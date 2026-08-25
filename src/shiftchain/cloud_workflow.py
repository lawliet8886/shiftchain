from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any

from google.api_core.exceptions import AlreadyExists
from google.cloud import firestore

from shiftchain.agent import ShiftChainToolRuntime, run_event_through_adk
from shiftchain.cloud_config import CloudConfig
from shiftchain.engine import ReconciliationEngine
from shiftchain.firestore_repository import FirestoreRepository
from shiftchain.models import ConfirmationStatus, RequestState
from shiftchain.observability import log_event
from shiftchain.parser import GeminiIntentParser
from shiftchain.tasks import CloudTaskScheduler, ResumePayload

LOGGER = logging.getLogger("shiftchain.cloud_workflow")


class FutureGenerationError(RuntimeError):
    pass


@dataclass
class CloudWorkflow:
    config: CloudConfig
    client: firestore.Client
    scheduler: CloudTaskScheduler

    @classmethod
    def from_config(cls, config: CloudConfig) -> "CloudWorkflow":
        client = firestore.Client(project=config.project_id, database=config.firestore_database)
        return cls(config=config, client=client, scheduler=CloudTaskScheduler(config))

    def repository(self, run_id: str) -> FirestoreRepository:
        return FirestoreRepository(self.client, run_id)

    def reset(self) -> dict[str, Any]:
        run_id = FirestoreRepository.next_demo_run_id(self.client)
        try:
            FirestoreRepository.seed_frozen_run(self.client, run_id)
        except AlreadyExists:
            run_id = FirestoreRepository.next_demo_run_id(self.client)
            FirestoreRepository.seed_frozen_run(self.client, run_id)
        log_event(LOGGER, "demo_run_seeded", run_id=run_id, operation="reset", result="PASS")
        return {"run_id": run_id, "status": "SEEDED"}

    async def deliver(self, run_id: str, event_id: str) -> dict[str, Any]:
        started = datetime.now(timezone.utc)
        repository = self.repository(run_id)
        event = repository.get_event(event_id)
        if event is None:
            raise KeyError(f"event not found: {event_id}")
        parser = GeminiIntentParser()
        runtime = ShiftChainToolRuntime(repository, parser)
        adk_result = await run_event_through_adk(runtime, event_id)
        stored_request = repository.get_request(event.request_id)
        if stored_request is None:
            raise RuntimeError("ADK flow did not persist the request")
        response: dict[str, Any] = {
            "run_id": run_id,
            "event_id": event_id,
            "request_id": event.request_id,
            "workflow_status": stored_request.state.value,
            "adk": adk_result,
        }

        if event_id == "EVT-003" and stored_request.state == RequestState.WAITING_CONFIRMATION:
            metadata = repository.event_metadata(event_id) or {}
            current_generation = int(metadata.get("resume_generation", 0))
            generation = current_generation + 1
            payload = ResumePayload(
                run_id=run_id,
                target_event_id="EVT-003",
                resume_generation=generation,
            )
            scheduled = self.scheduler.create(payload)
            persisted = repository.persist_schedule(
                event_id,
                expected_generation=current_generation,
                resume_generation=generation,
                task_name=scheduled.name,
                schedule_at=scheduled.schedule_at,
            )
            response["task"] = {
                "name": scheduled.name,
                "schedule_at": scheduled.schedule_at,
                "resume_generation": generation,
                "already_exists": scheduled.already_exists,
                "schedule_persisted": persisted,
            }

        if event_id == "EVT-004" and stored_request.state == RequestState.VERIFIED:
            intent = runtime.parsed.get(event_id) or stored_request.intent
            if intent is None or not intent.target_request_id or not intent.confirmation_by_worker_id:
                raise RuntimeError("confirmation intent missing after ADK execution")
            target_request = repository.get_request(intent.target_request_id)
            if target_request is None:
                raise RuntimeError("confirmation target request missing")
            target_metadata = repository.event_metadata(target_request.source_event_id) or {}
            if target_metadata.get("workflow_status") == RequestState.VERIFIED.value:
                response["confirmation_schedule_result"] = "TARGET_ALREADY_VERIFIED"
            elif target_metadata.get("confirmation_evidence"):
                response["confirmation_schedule_result"] = "CONFIRMATION_ALREADY_RECORDED"
            else:
                current_generation = int(target_metadata.get("resume_generation", 0))
                next_generation = current_generation + 1
                payload = ResumePayload(
                    run_id=run_id,
                    target_event_id=target_request.source_event_id,
                    resume_generation=next_generation,
                )
                scheduled = self.scheduler.create(payload, delay_seconds=0)
                schedule_result = repository.record_confirmation_and_schedule(
                    confirmation_event_id=event_id,
                    target_request_id=intent.target_request_id,
                    confirmer_worker_id=intent.confirmation_by_worker_id,
                    evidence=[item.model_dump(mode="json") for item in intent.evidence],
                    expected_generation=current_generation,
                    resume_generation=next_generation,
                    task_name=scheduled.name,
                    schedule_at=scheduled.schedule_at,
                )
                response["confirmation_task"] = {
                    "name": scheduled.name,
                    "schedule_at": scheduled.schedule_at,
                    "resume_generation": next_generation,
                    "already_exists": scheduled.already_exists,
                }
                response["confirmation_schedule_result"] = schedule_result
            response["confirmation_recorded_for"] = intent.target_request_id

        latency_ms = round((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        log_event(
            LOGGER,
            "cloud_event_delivered",
            run_id=run_id,
            source_event_id=event_id,
            request_id=event.request_id,
            workflow_status=stored_request.state.value,
            operation="deliver",
            result="PASS",
            latency_ms=latency_ms,
        )
        return response

    def resume(self, payload: ResumePayload, *, task_name: str | None, task_attempt: str | None) -> tuple[int, dict[str, Any]]:
        if payload.reason == "SMOKE_TEST":
            log_event(
                LOGGER,
                "task_smoke_received",
                run_id=payload.run_id,
                source_event_id=payload.target_event_id,
                task_name=task_name,
                task_attempt=task_attempt,
                resume_generation=payload.resume_generation,
                operation="resume_smoke",
                result="PASS",
            )
            return 204, {}

        repository = self.repository(payload.run_id)
        metadata = repository.event_metadata(payload.target_event_id)
        if metadata is None:
            raise KeyError("target event not found")
        persisted_generation = int(metadata.get("resume_generation", 0))
        if payload.resume_generation < persisted_generation:
            repository.record_resume_activity(
                payload.target_event_id,
                result="STALE_GENERATION_NO_OP",
                resume_generation=payload.resume_generation,
                task_name=task_name,
                task_attempt=task_attempt,
            )
            return 204, {"result": "STALE_GENERATION_NO_OP"}
        if payload.resume_generation > persisted_generation:
            raise FutureGenerationError("task generation is newer than persisted state")
        if metadata.get("workflow_status") == RequestState.VERIFIED.value:
            repository.record_resume_activity(
                payload.target_event_id,
                result="ALREADY_VERIFIED_NO_OP",
                resume_generation=payload.resume_generation,
                task_name=task_name,
                task_attempt=task_attempt,
            )
            return 204, {"result": "ALREADY_VERIFIED_NO_OP"}
        confirmation = metadata.get("confirmation_evidence")
        if not confirmation:
            repository.record_resume_activity(
                payload.target_event_id,
                result="WAIT_CONDITION_NOT_MET",
                resume_generation=payload.resume_generation,
                task_name=task_name,
                task_attempt=task_attempt,
            )
            return 204, {"result": "STILL_WAITING_CONFIRMATION"}

        request_id = metadata["request_id"]
        request = repository.get_request(request_id)
        if request is None or request.intent is None:
            raise RuntimeError("resume checkpoint is incomplete")
        resumed_intent = request.intent.model_copy(
            update={
                "confirmation": ConfirmationStatus.PRESENT,
                "confirmation_by_worker_id": confirmation["confirmed_by_worker_id"],
            }
        )
        result = ReconciliationEngine(repository).process(payload.target_event_id, resumed_intent)
        run = repository.get_run(payload.run_id)
        shift = run.shifts[resumed_intent.shift_id] if run and resumed_intent.shift_id else None
        log_event(
            LOGGER,
            "task_resume_completed",
            run_id=payload.run_id,
            source_event_id=payload.target_event_id,
            request_id=request_id,
            task_name=task_name,
            task_attempt=task_attempt,
            resume_generation=payload.resume_generation,
            shift_id=resumed_intent.shift_id,
            workflow_status=result.state.value,
            shift_version=shift.version if shift else None,
            schedule_version=run.schedule_version if run else None,
            idempotency_key=metadata.get("idempotency_key"),
            operation="resume",
            result="PASS" if result.state == RequestState.VERIFIED else "FAIL",
        )
        status_code = 200 if result.state == RequestState.VERIFIED else 409
        return status_code, {
            "result": result.model_dump(mode="json"),
            "current_owner_id": shift.current_owner_id if shift else None,
            "shift_version": shift.version if shift else None,
            "schedule_version": run.schedule_version if run else None,
        }

    def snapshot(self, run_id: str) -> dict[str, Any] | None:
        return self.repository(run_id).snapshot()
