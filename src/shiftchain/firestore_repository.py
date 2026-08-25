from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, TypeVar

from google.api_core.exceptions import AlreadyExists
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from shiftchain.frozen_data import frozen_events, frozen_run
from shiftchain.models import (
    AvailabilityWindow,
    CommitResult,
    CustodyLedgerEvent,
    LedgerEventType,
    RequestRecord,
    RequestState,
    ScheduleRun,
    Shift,
    SourceEvent,
    StructuredIntent,
    TransferCommit,
    VerificationRecord,
    Worker,
)
from shiftchain.repository import ShiftChainRepository, initial_ledger_for
from shiftchain.reliability import LOST_ACK_AFTER_VERIFY_ONCE, NoOpVerificationResult

T = TypeVar("T")
TransactionRunner = Callable[[Callable[[Any], T]], T]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


class FirestoreRepository(ShiftChainRepository):
    """Firestore adapter for the frozen domain contract.

    The repository is bound to one run for request lookups, while every public
    mutation still checks the run ID supplied by the deterministic engine.
    """

    def __init__(
        self,
        client: firestore.Client,
        run_id: str,
        transaction_runner: TransactionRunner | None = None,
    ) -> None:
        self.client = client
        self.run_id = run_id
        self._transaction_runner = transaction_runner or self._google_transaction_runner

    @classmethod
    def from_project(cls, project_id: str, database: str, run_id: str) -> "FirestoreRepository":
        return cls(firestore.Client(project=project_id, database=database), run_id)

    def _google_transaction_runner(self, callback: Callable[[Any], T]) -> T:
        wrapped = firestore.transactional(callback)
        return wrapped(self.client.transaction())

    def _run_ref(self, run_id: str | None = None):
        return self.client.collection("runs").document(run_id or self.run_id)

    def _event_ref(self, event_id: str, run_id: str | None = None):
        return self._run_ref(run_id).collection("events").document(event_id)

    def _ledger_ref(self, ledger_id: str, run_id: str | None = None):
        return self._run_ref(run_id).collection("ledger").document(ledger_id)

    @staticmethod
    def _run_to_document(run: ScheduleRun) -> dict[str, Any]:
        return {
            "run_id": run.run_id,
            "organization": run.organization,
            "mode": "DEMO",
            "authorized": run.authorized,
            "schedule_version": run.schedule_version,
            "period_start": run.period_start,
            "period_end": run.period_end,
            "expires_at": run.expires_at,
            "workers": {
                worker_id: {
                    "worker_id": worker.worker_id,
                    "name": worker.name,
                    "role": worker.role,
                    "availability": [window.model_dump(mode="python") for window in worker.availability],
                }
                for worker_id, worker in run.workers.items()
            },
            "shifts": {
                shift_id: {
                    "shift_id": shift.shift_id,
                    "label": shift.label,
                    "starts_at": shift.start_at,
                    "ends_at": shift.end_at,
                    "original_owner_id": shift.original_owner_id,
                    "current_owner_id": shift.current_owner_id,
                    "version": shift.version,
                    "custody_head_event_id": shift.custody_head_id,
                }
                for shift_id, shift in run.shifts.items()
            },
            "fault_injection": None,
            "failure_injection_used": False,
            "created_at": _utcnow(),
            "updated_at": _utcnow(),
        }

    @staticmethod
    def _run_from_document(document: dict[str, Any]) -> ScheduleRun:
        workers = {}
        for worker_id, raw in document["workers"].items():
            workers[worker_id] = Worker(
                worker_id=raw["worker_id"],
                name=raw["name"],
                role=raw["role"],
                availability=tuple(
                    AvailabilityWindow(
                        start_at=_as_datetime(window["start_at"]),
                        end_at=_as_datetime(window["end_at"]),
                    )
                    for window in raw["availability"]
                ),
            )
        shifts = {}
        for shift_id, raw in document["shifts"].items():
            shifts[shift_id] = Shift(
                shift_id=raw["shift_id"],
                label=raw["label"],
                start_at=_as_datetime(raw["starts_at"]),
                end_at=_as_datetime(raw["ends_at"]),
                original_owner_id=raw["original_owner_id"],
                current_owner_id=raw["current_owner_id"],
                version=int(raw["version"]),
                custody_head_id=raw["custody_head_event_id"],
            )
        return ScheduleRun(
            run_id=document["run_id"],
            organization=document["organization"],
            period_start=_as_datetime(document["period_start"]),
            period_end=_as_datetime(document["period_end"]),
            schedule_version=int(document["schedule_version"]),
            authorized=bool(document["authorized"]),
            expires_at=_as_datetime(document["expires_at"]),
            workers=workers,
            shifts=shifts,
        )

    @staticmethod
    def _event_to_document(event: SourceEvent) -> dict[str, Any]:
        return {
            "event_id": event.event_id,
            "request_id": event.request_id,
            "source_message": event.message,
            "source_timestamp": event.occurred_at,
            "workflow_status": RequestState.RECEIVED.value,
            "intent": None,
            "validation_decision": None,
            "target_event_id": None,
            "expected_shift_version": None,
            "expected_custody_head_event_id": None,
            "idempotency_key": f"request:{event.run_id}:{event.request_id}",
            "resume_generation": 0,
            "scheduled_task_name": None,
            "confirmation_evidence": None,
            "activity": [],
            "retry_count": 0,
            "next_attempt_at": None,
            "last_attempt": None,
            "last_result": None,
            "last_error": None,
            "applied_ledger_id": None,
            "created_at": _utcnow(),
            "updated_at": _utcnow(),
        }

    @staticmethod
    def _ledger_to_document(entry: CustodyLedgerEvent) -> dict[str, Any]:
        event_type = entry.event_type.value
        return {
            "ledger_event_id": entry.ledger_id,
            "event_type": event_type,
            "run_id": entry.run_id,
            "shift_id": entry.shift_id,
            "request_id": entry.request_id,
            "source_event_id": entry.source_event_id,
            "from_worker_id": entry.from_worker_id,
            "to_worker_id": entry.to_worker_id,
            "predecessor_id": entry.predecessor_id,
            "shift_version": entry.shift_version,
            "schedule_version": entry.schedule_version,
            "idempotency_key": f"ledger:{entry.run_id}:{entry.request_id or entry.ledger_id}",
            "occurred_at": entry.occurred_at,
            "created_at": _utcnow(),
        }

    @staticmethod
    def _ledger_from_document(document: dict[str, Any]) -> CustodyLedgerEvent:
        return CustodyLedgerEvent(
            ledger_id=document["ledger_event_id"],
            event_type=LedgerEventType(document["event_type"]),
            run_id=document["run_id"],
            shift_id=document["shift_id"],
            request_id=document.get("request_id"),
            source_event_id=document.get("source_event_id"),
            from_worker_id=document.get("from_worker_id"),
            to_worker_id=document["to_worker_id"],
            predecessor_id=document.get("predecessor_id"),
            shift_version=int(document["shift_version"]),
            schedule_version=int(document["schedule_version"]),
            occurred_at=_as_datetime(document["occurred_at"]),
        )

    @classmethod
    def seed_frozen_run(
        cls,
        client: firestore.Client,
        run_id: str,
        *,
        create_only: bool = True,
    ) -> "FirestoreRepository":
        run = frozen_run().model_copy(update={"run_id": run_id})
        events = tuple(event.model_copy(update={"run_id": run_id}) for event in frozen_events())
        repository = cls(client, run_id)
        run_ref = repository._run_ref()
        if create_only and run_ref.get().exists:
            raise AlreadyExists(f"run already exists: {run_id}")
        batch = client.batch()
        batch.set(run_ref, cls._run_to_document(run))
        for event in events:
            batch.set(repository._event_ref(event.event_id), cls._event_to_document(event))
        for entry in initial_ledger_for(run, run.period_start):
            batch.set(repository._ledger_ref(entry.ledger_id), cls._ledger_to_document(entry))
        batch.commit()
        return repository

    @classmethod
    def next_demo_run_id(cls, client: firestore.Client) -> str:
        pattern = re.compile(r"^RUN-DEMO-(\d{3})$")
        numbers = []
        for ref in client.collection("runs").list_documents():
            match = pattern.match(ref.id)
            if match:
                numbers.append(int(match.group(1)))
        return f"RUN-DEMO-{max(numbers, default=0) + 1:03d}"

    def get_run(self, run_id: str) -> ScheduleRun | None:
        snapshot = self._run_ref(run_id).get()
        return self._run_from_document(snapshot.to_dict()) if snapshot.exists else None

    def get_event(self, event_id: str) -> SourceEvent | None:
        snapshot = self._event_ref(event_id).get()
        if not snapshot.exists:
            return None
        raw = snapshot.to_dict()
        return SourceEvent(
            event_id=event_id,
            request_id=raw["request_id"],
            run_id=self.run_id,
            occurred_at=_as_datetime(raw["source_timestamp"]),
            message=raw["source_message"],
        )

    def _request_from_snapshot(self, snapshot) -> RequestRecord | None:
        if snapshot is None or not snapshot.exists:
            return None
        raw = snapshot.to_dict()
        intent = StructuredIntent.model_validate(raw["intent"]) if raw.get("intent") else None
        decision = raw.get("validation_decision") or {}
        return RequestRecord(
            request_id=raw["request_id"],
            source_event_id=raw["event_id"],
            run_id=self.run_id,
            state=RequestState(raw["workflow_status"]),
            intent=intent,
            reason_codes=tuple(decision.get("reason_codes", ())),
            applied_ledger_id=raw.get("applied_ledger_id"),
            expected_schedule_version=decision.get("expected_schedule_version"),
            expected_shift_version=raw.get("expected_shift_version"),
        )

    def get_request(self, request_id: str) -> RequestRecord | None:
        query = (
            self._run_ref()
            .collection("events")
            .where(filter=FieldFilter("request_id", "==", request_id))
            .limit(1)
        )
        snapshots = list(query.stream())
        return self._request_from_snapshot(snapshots[0]) if snapshots else None

    def save_request(self, request: RequestRecord) -> None:
        self._event_ref(request.source_event_id).set(
            {
                "workflow_status": request.state.value,
                "intent": request.intent.model_dump(mode="python") if request.intent else None,
                "validation_decision": {
                    "reason_codes": list(request.reason_codes),
                    "expected_schedule_version": request.expected_schedule_version,
                },
                "expected_shift_version": request.expected_shift_version,
                "applied_ledger_id": request.applied_ledger_id,
                "last_result": request.state.value,
                "updated_at": _utcnow(),
            },
            merge=True,
        )

    def commit_transfer(self, command: TransferCommit) -> CommitResult:
        run_ref = self._run_ref(command.run_id)
        event_ref = self._event_ref(command.source_event_id, command.run_id)
        predecessor_ref = self._ledger_ref(command.expected_custody_head_id, command.run_id)
        new_shift_version = command.expected_shift_version + 1
        ledger_id = f"ledger:{command.request_id}:v{new_shift_version}"
        ledger_ref = self._ledger_ref(ledger_id, command.run_id)
        recorded_at = _utcnow()

        def callback(transaction) -> CommitResult:
            run_snapshot = run_ref.get(transaction=transaction)
            event_snapshot = event_ref.get(transaction=transaction)
            predecessor_snapshot = predecessor_ref.get(transaction=transaction)
            ledger_snapshot = ledger_ref.get(transaction=transaction)
            if not run_snapshot.exists:
                return CommitResult(applied=False, idempotent=False, conflict_code="RUN_NOT_FOUND")
            if not event_snapshot.exists:
                return CommitResult(applied=False, idempotent=False, conflict_code="EVENT_NOT_FOUND")
            event_doc = event_snapshot.to_dict()
            if event_doc.get("applied_ledger_id"):
                existing_ref = self._ledger_ref(event_doc["applied_ledger_id"], command.run_id)
                existing_snapshot = existing_ref.get(transaction=transaction)
                if existing_snapshot.exists:
                    return CommitResult(
                        applied=False,
                        idempotent=True,
                        ledger_event=self._ledger_from_document(existing_snapshot.to_dict()),
                    )
            if ledger_snapshot.exists:
                return CommitResult(
                    applied=False,
                    idempotent=True,
                    ledger_event=self._ledger_from_document(ledger_snapshot.to_dict()),
                )
            if not predecessor_snapshot.exists:
                return CommitResult(applied=False, idempotent=False, conflict_code="PREDECESSOR_NOT_FOUND")
            run_doc = deepcopy(run_snapshot.to_dict())
            shift = run_doc["shifts"].get(command.shift_id)
            if shift is None:
                return CommitResult(applied=False, idempotent=False, conflict_code="SHIFT_NOT_FOUND")
            comparisons = (
                (int(run_doc["schedule_version"]) == command.expected_schedule_version, "SCHEDULE_VERSION_CONFLICT"),
                (int(shift["version"]) == command.expected_shift_version, "SHIFT_VERSION_CONFLICT"),
                (shift["custody_head_event_id"] == command.expected_custody_head_id, "CUSTODY_HEAD_CONFLICT"),
                (shift["current_owner_id"] == command.from_worker_id, "CURRENT_OWNER_CONFLICT"),
            )
            for passed, code in comparisons:
                if not passed:
                    return CommitResult(applied=False, idempotent=False, conflict_code=code)
            intent = event_doc.get("intent") or {}
            if intent.get("confirmation") != "PRESENT":
                return CommitResult(applied=False, idempotent=False, conflict_code="CONFIRMATION_MISSING")
            if intent.get("confirmation_by_worker_id") != command.to_worker_id:
                return CommitResult(applied=False, idempotent=False, conflict_code="CONFIRMATION_WORKER_MISMATCH")

            new_schedule_version = command.expected_schedule_version + 1
            entry = CustodyLedgerEvent(
                ledger_id=ledger_id,
                event_type=LedgerEventType.TRANSFER_APPLIED,
                run_id=command.run_id,
                shift_id=command.shift_id,
                request_id=command.request_id,
                source_event_id=command.source_event_id,
                from_worker_id=command.from_worker_id,
                to_worker_id=command.to_worker_id,
                predecessor_id=command.expected_custody_head_id,
                shift_version=new_shift_version,
                schedule_version=new_schedule_version,
                occurred_at=command.occurred_at,
            )
            shift["current_owner_id"] = command.to_worker_id
            shift["version"] = new_shift_version
            shift["custody_head_event_id"] = ledger_id
            run_doc["schedule_version"] = new_schedule_version
            run_doc["updated_at"] = recorded_at
            ledger_doc = self._ledger_to_document(entry)
            ledger_doc["created_at"] = recorded_at
            transaction.set(ledger_ref, ledger_doc)
            transaction.update(run_ref, {"shifts": run_doc["shifts"], "schedule_version": new_schedule_version, "updated_at": recorded_at})
            transaction.update(event_ref, {"workflow_status": RequestState.APPLIED.value, "applied_ledger_id": ledger_id, "last_result": RequestState.APPLIED.value, "updated_at": recorded_at})
            return CommitResult(applied=True, idempotent=False, ledger_event=entry)

        return self._transaction_runner(callback)

    def get_ledger_event(self, ledger_id: str) -> CustodyLedgerEvent | None:
        snapshot = self._ledger_ref(ledger_id).get()
        if not snapshot.exists:
            return None
        raw = snapshot.to_dict()
        if raw.get("event_type") in {
            LedgerEventType.TRANSFER_VERIFIED.value,
            LedgerEventType.NO_OP_VERIFIED.value,
        }:
            return None
        return self._ledger_from_document(raw)

    def custody_chain(self, shift_id: str) -> tuple[CustodyLedgerEvent, ...]:
        run = self.get_run(self.run_id)
        if run is None or shift_id not in run.shifts:
            return ()
        cursor = run.shifts[shift_id].custody_head_id
        reverse_chain: list[CustodyLedgerEvent] = []
        seen: set[str] = set()
        while cursor:
            if cursor in seen:
                raise RuntimeError("custody ledger cycle detected")
            seen.add(cursor)
            entry = self.get_ledger_event(cursor)
            if entry is None:
                raise RuntimeError(f"custody ledger entry missing: {cursor}")
            reverse_chain.append(entry)
            cursor = entry.predecessor_id
        return tuple(reversed(reverse_chain))

    def save_verification(self, record: VerificationRecord) -> None:
        request = self.get_request(record.request_id)
        if request is None or not request.applied_ledger_id:
            raise RuntimeError("cannot verify request without applied ledger")
        event_ref = self._event_ref(request.source_event_id)
        applied_ref = self._ledger_ref(request.applied_ledger_id)
        verification_ref = self._ledger_ref(record.verification_id)

        def callback(transaction) -> None:
            event_snapshot = event_ref.get(transaction=transaction)
            applied_snapshot = applied_ref.get(transaction=transaction)
            verification_snapshot = verification_ref.get(transaction=transaction)
            if verification_snapshot.exists:
                return
            if not event_snapshot.exists or not applied_snapshot.exists:
                raise RuntimeError("verification readback disappeared")
            applied = applied_snapshot.to_dict()
            verification_doc = {
                "ledger_event_id": record.verification_id,
                "event_type": LedgerEventType.TRANSFER_VERIFIED.value,
                "run_id": self.run_id,
                "shift_id": applied["shift_id"],
                "request_id": record.request_id,
                "source_event_id": applied["source_event_id"],
                "from_worker_id": applied["from_worker_id"],
                "to_worker_id": applied["to_worker_id"],
                "predecessor_id": applied["ledger_event_id"],
                "shift_version": applied["shift_version"],
                "schedule_version": applied["schedule_version"],
                "idempotency_key": f"verify:{self.run_id}:{record.request_id}",
                "checks": list(record.checks),
                "occurred_at": record.verified_at,
                "created_at": record.verified_at,
            }
            transaction.set(verification_ref, verification_doc)
            transaction.update(event_ref, {"workflow_status": RequestState.VERIFIED.value, "verification_id": record.verification_id, "last_result": RequestState.VERIFIED.value, "updated_at": record.verified_at})

        self._transaction_runner(callback)

    def get_verification(self, request_id: str) -> VerificationRecord | None:
        snapshot = self._ledger_ref(f"verify:{request_id}").get()
        if not snapshot.exists:
            return None
        raw = snapshot.to_dict()
        return VerificationRecord(
            verification_id=raw["ledger_event_id"],
            request_id=raw["request_id"],
            ledger_id=raw["predecessor_id"],
            verified_at=_as_datetime(raw["occurred_at"]),
            checks=tuple(raw.get("checks", ())),
        )

    def event_metadata(self, event_id: str) -> dict[str, Any] | None:
        snapshot = self._event_ref(event_id).get()
        return snapshot.to_dict() if snapshot.exists else None

    def persist_schedule(
        self,
        event_id: str,
        *,
        expected_generation: int,
        resume_generation: int,
        task_name: str,
        schedule_at: datetime,
    ) -> bool:
        event_ref = self._event_ref(event_id)
        updated_at = _utcnow()

        def callback(transaction) -> bool:
            snapshot = event_ref.get(transaction=transaction)
            if not snapshot.exists:
                raise RuntimeError("event missing while persisting schedule")
            raw = snapshot.to_dict()
            current = int(raw.get("resume_generation", 0))
            if current == resume_generation and raw.get("scheduled_task_name") == task_name:
                return True
            if current != expected_generation or raw.get("workflow_status") != RequestState.WAITING_CONFIRMATION.value:
                return False
            transaction.update(
                event_ref,
                {
                    "resume_generation": resume_generation,
                    "scheduled_task_name": task_name,
                    "next_attempt_at": schedule_at,
                    "last_result": "TASK_SCHEDULED",
                    "updated_at": updated_at,
                },
            )
            return True

        return self._transaction_runner(callback)

    def record_confirmation_and_schedule(
        self,
        confirmation_event_id: str,
        target_request_id: str,
        confirmer_worker_id: str,
        evidence: list[dict[str, Any]],
        *,
        expected_generation: int,
        resume_generation: int,
        task_name: str,
        schedule_at: datetime,
    ) -> str:
        """Atomically persist confirmation evidence and its new resume generation.

        The Cloud Task is intentionally created before this transaction. A task
        that wins the race sees a future generation and retries without mutation.
        """
        confirmation_ref = self._event_ref(confirmation_event_id)
        target = self.get_request(target_request_id)
        if target is None:
            raise RuntimeError("target request not found")
        target_ref = self._event_ref(target.source_event_id)
        recorded_at = _utcnow()

        def callback(transaction) -> str:
            confirmation_snapshot = confirmation_ref.get(transaction=transaction)
            target_snapshot = target_ref.get(transaction=transaction)
            if not confirmation_snapshot.exists or not target_snapshot.exists:
                raise RuntimeError("confirmation documents missing")
            confirmation_doc = confirmation_snapshot.to_dict()
            target_doc = target_snapshot.to_dict()
            if confirmation_doc.get("workflow_status") != RequestState.VERIFIED.value:
                raise RuntimeError("confirmation event is not verified")
            if target_doc.get("workflow_status") == RequestState.VERIFIED.value:
                return "TARGET_ALREADY_VERIFIED"
            if target_doc.get("workflow_status") != RequestState.WAITING_CONFIRMATION.value:
                raise RuntimeError("target request is not waiting")
            current_generation = int(target_doc.get("resume_generation", 0))
            existing_confirmation = target_doc.get("confirmation_evidence")
            if existing_confirmation:
                return "CONFIRMATION_ALREADY_RECORDED"
            if current_generation != expected_generation:
                return "GENERATION_CONFLICT"
            activity = list(target_doc.get("activity") or [])
            activity.append(
                {
                    "result": "CONFIRMATION_RECORDED_RESUME_SCHEDULED",
                    "source_event_id": confirmation_event_id,
                    "resume_generation": resume_generation,
                    "task_name": task_name,
                    "occurred_at": recorded_at,
                }
            )
            transaction.update(
                target_ref,
                {
                    "confirmation_evidence": {
                        "source_event_id": confirmation_event_id,
                        "confirmed_by_worker_id": confirmer_worker_id,
                        "decision": "ACCEPT",
                        "evidence": evidence,
                        "recorded_at": recorded_at,
                    },
                    "resume_generation": resume_generation,
                    "scheduled_task_name": task_name,
                    "next_attempt_at": schedule_at,
                    "activity": activity,
                    "last_result": "CONFIRMATION_RECORDED_RESUME_SCHEDULED",
                    "updated_at": recorded_at,
                },
            )
            transaction.update(
                confirmation_ref,
                {
                    "last_result": "CONFIRMATION_RECORDED_RESUME_SCHEDULED",
                    "target_event_id": target.source_event_id,
                    "scheduled_task_name": task_name,
                    "resume_generation": resume_generation,
                    "updated_at": recorded_at,
                },
            )
            return "CONFIRMATION_RECORDED_RESUME_SCHEDULED"

        return self._transaction_runner(callback)

    def record_resume_activity(
        self,
        event_id: str,
        *,
        result: str,
        resume_generation: int,
        task_name: str | None,
        task_attempt: str | None,
    ) -> None:
        event_ref = self._event_ref(event_id)
        recorded_at = _utcnow()

        def callback(transaction) -> None:
            snapshot = event_ref.get(transaction=transaction)
            if not snapshot.exists:
                raise RuntimeError("resume event missing")
            raw = snapshot.to_dict()
            activity = list(raw.get("activity") or [])
            duplicate = any(
                item.get("result") == result
                and int(item.get("resume_generation", -1)) == resume_generation
                and item.get("task_name") == task_name
                for item in activity
            )
            if not duplicate:
                activity.append(
                    {
                        "result": result,
                        "resume_generation": resume_generation,
                        "task_name": task_name,
                        "task_attempt": task_attempt,
                        "occurred_at": recorded_at,
                    }
                )
            transaction.update(
                event_ref,
                {
                    "activity": activity,
                    "last_attempt": recorded_at,
                    "last_result": result,
                    "updated_at": recorded_at,
                },
            )

        self._transaction_runner(callback)

    def configure_failure_injection(self, injection: str) -> bool:
        """Explicitly enable the one supported reliability fault on a DEMO run."""
        if injection != LOST_ACK_AFTER_VERIFY_ONCE:
            raise ValueError("unsupported failure injection")
        run_ref = self._run_ref()
        configured_at = _utcnow()

        def callback(transaction) -> bool:
            snapshot = run_ref.get(transaction=transaction)
            if not snapshot.exists:
                raise RuntimeError("run not found")
            raw = snapshot.to_dict()
            if raw.get("mode") != "DEMO":
                return False
            transaction.update(
                run_ref,
                {
                    "fault_injection": injection,
                    "failure_injection_used": False,
                    "failure_injection_configured_at": configured_at,
                    "failure_injection_consumed_at": None,
                    "updated_at": configured_at,
                },
            )
            return True

        return self._transaction_runner(callback)

    def consume_failure_injection(
        self,
        target_event_id: str,
        *,
        resume_generation: int | None = None,
        task_name: str | None = None,
        task_attempt: str | None = None,
    ) -> bool:
        """Atomically consume the lost-ack fault, but only after durable VERIFIED."""
        run_ref = self._run_ref()
        event_ref = self._event_ref(target_event_id)
        consumed_at = _utcnow()

        def callback(transaction) -> bool:
            run_snapshot = run_ref.get(transaction=transaction)
            event_snapshot = event_ref.get(transaction=transaction)
            if not run_snapshot.exists or not event_snapshot.exists:
                return False
            run_doc = run_snapshot.to_dict()
            event_doc = event_snapshot.to_dict()
            verification_id = event_doc.get("verification_id")
            if not verification_id:
                return False
            verification_snapshot = self._ledger_ref(verification_id).get(transaction=transaction)
            eligible = (
                run_doc.get("mode") == "DEMO"
                and run_doc.get("fault_injection") == LOST_ACK_AFTER_VERIFY_ONCE
                and run_doc.get("failure_injection_used") is False
                and event_doc.get("request_id") == "REQ-003"
                and event_doc.get("workflow_status") == RequestState.VERIFIED.value
                and verification_snapshot.exists
                and verification_snapshot.to_dict().get("event_type") == LedgerEventType.TRANSFER_VERIFIED.value
            )
            if not eligible:
                return False
            activity = list(event_doc.get("activity") or [])
            activity.append(
                {
                    "result": "HTTP_ACKNOWLEDGEMENT_INTENTIONALLY_FAILED",
                    "http_status": 503,
                    "resume_generation": resume_generation,
                    "task_name": task_name,
                    "task_attempt": task_attempt,
                    "occurred_at": consumed_at,
                }
            )
            transaction.update(
                run_ref,
                {
                    "failure_injection_used": True,
                    "failure_injection_consumed_at": consumed_at,
                    "failure_injection_target_event_id": target_event_id,
                    "failure_injection_resume_generation": resume_generation,
                    "failure_injection_task_name": task_name,
                    "failure_injection_task_attempt": task_attempt,
                    "failure_injection_http_status": 503,
                    "updated_at": consumed_at,
                },
            )
            transaction.update(
                event_ref,
                {
                    "activity": activity,
                    "last_attempt": consumed_at,
                    "last_result": "HTTP_ACKNOWLEDGEMENT_INTENTIONALLY_FAILED",
                    "updated_at": consumed_at,
                },
            )
            return True

        return self._transaction_runner(callback)

    def verify_existing_effect(
        self,
        target_event_id: str,
        *,
        resume_generation: int,
        task_name: str | None,
        task_attempt: str | None,
    ) -> NoOpVerificationResult:
        """Read before repeat and record deterministic non-custody evidence."""
        run_ref = self._run_ref()
        event_ref = self._event_ref(target_event_id)
        ledger_collection = self._run_ref().collection("ledger")
        evidence_id = f"noop:{target_event_id}:g{resume_generation}"
        noop_ref = self._ledger_ref(evidence_id)
        recorded_at = _utcnow()

        def callback(transaction) -> NoOpVerificationResult:
            run_snapshot = run_ref.get(transaction=transaction)
            event_snapshot = event_ref.get(transaction=transaction)
            noop_snapshot = noop_ref.get(transaction=transaction)
            if not run_snapshot.exists or not event_snapshot.exists:
                return NoOpVerificationResult(False, None, ("RUN_OR_EVENT_MISSING",))
            run_doc = run_snapshot.to_dict()
            event_doc = event_snapshot.to_dict()
            intent = event_doc.get("intent") or {}
            applied_id = event_doc.get("applied_ledger_id")
            verification_id = event_doc.get("verification_id") or f"verify:{event_doc.get('request_id', '')}"
            if not applied_id:
                return NoOpVerificationResult(False, None, ("APPLIED_LEDGER_ID_MISSING",))
            applied_snapshot = self._ledger_ref(applied_id).get(transaction=transaction)
            verification_snapshot = self._ledger_ref(verification_id).get(transaction=transaction)
            ledger_snapshots = list(ledger_collection.stream(transaction=transaction))
            applied_doc = applied_snapshot.to_dict() if applied_snapshot.exists else {}
            verification_doc = verification_snapshot.to_dict() if verification_snapshot.exists else {}
            shift_id = intent.get("shift_id")
            shift = (run_doc.get("shifts") or {}).get(shift_id, {})
            predecessor_id = applied_doc.get("predecessor_id")
            predecessor_snapshot = self._ledger_ref(predecessor_id).get(transaction=transaction) if predecessor_id else None
            predecessor_doc = predecessor_snapshot.to_dict() if predecessor_snapshot and predecessor_snapshot.exists else {}
            request_id = event_doc.get("request_id")
            equivalent_applied = [
                snapshot.to_dict()
                for snapshot in ledger_snapshots
                if snapshot.to_dict().get("event_type") == LedgerEventType.TRANSFER_APPLIED.value
                and snapshot.to_dict().get("request_id") == request_id
            ]
            equivalent_verified = [
                snapshot.to_dict()
                for snapshot in ledger_snapshots
                if snapshot.to_dict().get("event_type") == LedgerEventType.TRANSFER_VERIFIED.value
                and snapshot.to_dict().get("request_id") == request_id
            ]
            expected_request_key = f"request:{self.run_id}:{request_id}"
            expected_ledger_key = f"ledger:{self.run_id}:{request_id}"
            checks = {
                "request_verified": event_doc.get("workflow_status") == RequestState.VERIFIED.value,
                "intent_present": bool(shift_id and intent.get("to_worker_id") and intent.get("from_worker_id")),
                "applied_present": applied_snapshot.exists,
                "applied_type": applied_doc.get("event_type") == LedgerEventType.TRANSFER_APPLIED.value,
                "applied_request": applied_doc.get("request_id") == request_id,
                "applied_workers": applied_doc.get("from_worker_id") == intent.get("from_worker_id") and applied_doc.get("to_worker_id") == intent.get("to_worker_id"),
                "applied_shift": applied_doc.get("shift_id") == shift_id,
                "verification_present": verification_snapshot.exists,
                "verification_type": verification_doc.get("event_type") == LedgerEventType.TRANSFER_VERIFIED.value,
                "verification_links_applied": verification_doc.get("predecessor_id") == applied_id,
                "verification_versions": verification_doc.get("shift_version") == applied_doc.get("shift_version") and verification_doc.get("schedule_version") == applied_doc.get("schedule_version"),
                "owner_matches": shift.get("current_owner_id") == intent.get("to_worker_id"),
                "head_matches": shift.get("custody_head_event_id") == applied_id,
                "shift_version_matches": shift.get("version") == applied_doc.get("shift_version"),
                "schedule_version_matches": run_doc.get("schedule_version") == applied_doc.get("schedule_version"),
                "predecessor_present": bool(predecessor_doc),
                "predecessor_owner_matches": predecessor_doc.get("to_worker_id") == intent.get("from_worker_id"),
                "request_idempotency_key": event_doc.get("idempotency_key") == expected_request_key,
                "ledger_idempotency_key": applied_doc.get("idempotency_key") == expected_ledger_key,
                "single_applied_effect": len(equivalent_applied) == 1,
                "single_verification": len(equivalent_verified) == 1,
            }
            errors = tuple(name for name, passed in checks.items() if not passed)
            if errors:
                return NoOpVerificationResult(
                    False,
                    None,
                    errors,
                    shift.get("current_owner_id"),
                    shift.get("version"),
                    run_doc.get("schedule_version"),
                    shift.get("custody_head_event_id"),
                )
            if not noop_snapshot.exists:
                digest_payload = {
                    "run_id": self.run_id,
                    "request_id": request_id,
                    "shift_id": shift_id,
                    "resume_generation": resume_generation,
                    "applied_id": applied_id,
                    "verification_id": verification_id,
                    "owner": shift["current_owner_id"],
                    "shift_version": shift["version"],
                    "schedule_version": run_doc["schedule_version"],
                    "custody_head": shift["custody_head_event_id"],
                }
                evidence_digest = hashlib.sha256(
                    json.dumps(digest_payload, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
                transaction.set(
                    noop_ref,
                    {
                        "ledger_event_id": evidence_id,
                        "record_type": LedgerEventType.NO_OP_VERIFIED.value,
                        "event_type": LedgerEventType.NO_OP_VERIFIED.value,
                        "run_id": self.run_id,
                        "request_id": request_id,
                        "source_event_id": target_event_id,
                        "shift_id": shift_id,
                        "resume_generation": resume_generation,
                        "applied_ledger_event_id": applied_id,
                        "verified_ledger_event_id": verification_id,
                        "observed_owner_id": shift["current_owner_id"],
                        "observed_shift_version": shift["version"],
                        "observed_schedule_version": run_doc["schedule_version"],
                        "custody_head_event_id": shift["custody_head_event_id"],
                        "idempotency_key": f"noop:{self.run_id}:{target_event_id}:g{resume_generation}",
                        "evidence_digest": evidence_digest,
                        "task_name": task_name,
                        "task_attempt": task_attempt,
                        "occurred_at": recorded_at,
                        "created_at": recorded_at,
                    },
                )
                activity = list(event_doc.get("activity") or [])
                activity.append(
                    {
                        "result": LedgerEventType.NO_OP_VERIFIED.value,
                        "evidence_id": evidence_id,
                        "resume_generation": resume_generation,
                        "task_name": task_name,
                        "task_attempt": task_attempt,
                        "occurred_at": recorded_at,
                    }
                )
                transaction.update(
                    event_ref,
                    {
                        "activity": activity,
                        "last_attempt": recorded_at,
                        "last_result": LedgerEventType.NO_OP_VERIFIED.value,
                        "updated_at": recorded_at,
                    },
                )
            return NoOpVerificationResult(
                True,
                evidence_id,
                (),
                shift["current_owner_id"],
                shift["version"],
                run_doc["schedule_version"],
                shift["custody_head_event_id"],
            )

        return self._transaction_runner(callback)

    def snapshot(self) -> dict[str, Any] | None:
        run_snapshot = self._run_ref().get()
        if not run_snapshot.exists:
            return None
        events = [snapshot.to_dict() for snapshot in self._run_ref().collection("events").stream()]
        ledger = [snapshot.to_dict() for snapshot in self._run_ref().collection("ledger").stream()]
        events.sort(key=lambda item: item["event_id"])
        ledger.sort(key=lambda item: (item.get("occurred_at") or datetime.min.replace(tzinfo=timezone.utc), item["ledger_event_id"]))
        return {"run": run_snapshot.to_dict(), "events": events, "ledger": ledger}
