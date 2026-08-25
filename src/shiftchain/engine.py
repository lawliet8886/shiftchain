from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import logging

from shiftchain.models import (
    ConfirmationDecision,
    ConfirmationStatus,
    IntentType,
    ProcessingResult,
    RequestRecord,
    RequestState,
    StructuredIntent,
    TransferCommit,
    ValidationDecision,
    VerificationRecord,
)
from shiftchain.repository import ShiftChainRepository
from shiftchain.observability import log_event

LOGGER = logging.getLogger("shiftchain.engine")


class ReconciliationEngine:
    """The sole authority for business validity and state mutation."""

    def __init__(self, repository: ShiftChainRepository, now: Callable[[], datetime] | None = None) -> None:
        self.repository = repository
        self._now = now or (lambda: datetime.now(timezone.utc))

    def process(self, event_id: str, intent: StructuredIntent) -> ProcessingResult:
        event = self.repository.get_event(event_id)
        if event is None:
            return ProcessingResult(
                source_event_id=event_id,
                request_id="UNKNOWN",
                state=RequestState.REJECTED,
                reason_codes=("EVENT_NOT_FOUND",),
            )
        if intent.source_event_id != event.event_id:
            return self._reject_unstored(event, "SOURCE_EVENT_MISMATCH")

        existing = self.repository.get_request(event.request_id)
        if existing and existing.state == RequestState.VERIFIED:
            return ProcessingResult(
                source_event_id=event_id,
                request_id=event.request_id,
                state=RequestState.VERIFIED,
                reason_codes=("IDEMPOTENT_REPLAY",),
                idempotent=True,
                ledger_id=existing.applied_ledger_id,
            )

        request = existing or RequestRecord(
            request_id=event.request_id,
            source_event_id=event.event_id,
            run_id=event.run_id,
        )
        request.intent = intent
        decision = self.validate(event.run_id, request, intent)
        request.state = decision.state
        request.reason_codes = decision.reason_codes
        request.expected_schedule_version = decision.expected_schedule_version
        request.expected_shift_version = decision.expected_shift_version
        self.repository.save_request(request)
        log_event(
            LOGGER,
            "validation_completed",
            event_id=event_id,
            request_id=request.request_id,
            state=decision.state.value,
            reason_codes=decision.reason_codes,
        )

        if intent.intent_type == IntentType.CONFIRM_REQUEST and decision.state == RequestState.READY:
            request.state = RequestState.VERIFIED
            request.reason_codes = ("CONFIRMATION_RULE_VERIFIED_NO_ASYNC_RESUME_IN_PHASE_1",)
            self.repository.save_request(request)
            return self._result(request)
        if decision.state != RequestState.READY:
            return self._result(request)

        event = self.repository.get_event(event_id)
        assert event is not None
        command = TransferCommit(
            run_id=event.run_id,
            request_id=event.request_id,
            source_event_id=event.event_id,
            shift_id=intent.shift_id or "",
            from_worker_id=intent.from_worker_id or "",
            to_worker_id=intent.to_worker_id or "",
            expected_schedule_version=decision.expected_schedule_version or 0,
            expected_shift_version=decision.expected_shift_version or 0,
            expected_custody_head_id=decision.expected_custody_head_id or "",
            occurred_at=event.occurred_at,
        )
        commit = self.repository.commit_transfer(command)
        if commit.idempotent:
            stored = self.repository.get_request(event.request_id)
            assert stored is not None
            return ProcessingResult(
                source_event_id=event_id,
                request_id=stored.request_id,
                state=stored.state,
                reason_codes=("IDEMPOTENT_COMMIT",),
                idempotent=True,
                ledger_id=stored.applied_ledger_id,
            )
        if not commit.applied or commit.ledger_event is None:
            request.state = RequestState.FAILED
            request.reason_codes = (commit.conflict_code or "COMMIT_FAILED",)
            self.repository.save_request(request)
            return self._result(request)

        request = self.repository.get_request(event.request_id)
        assert request is not None and request.state == RequestState.APPLIED
        return self.verify_outcome(request, commit.ledger_event.ledger_id)

    def validate(
        self,
        run_id: str,
        request: RequestRecord,
        intent: StructuredIntent,
    ) -> ValidationDecision:
        run = self.repository.get_run(run_id)
        if run is None:
            return ValidationDecision(state=RequestState.REJECTED, reason_codes=("RUN_NOT_FOUND",))
        if not run.authorized:
            return ValidationDecision(state=RequestState.REJECTED, reason_codes=("RUN_UNAUTHORIZED",))
        if self._now() > run.expires_at:
            return ValidationDecision(state=RequestState.REJECTED, reason_codes=("RUN_EXPIRED",))
        if intent.ambiguities or intent.intent_type == IntentType.UNKNOWN:
            return ValidationDecision(
                state=RequestState.NEEDS_CLARIFICATION,
                reason_codes=tuple(intent.ambiguities) or ("UNKNOWN_INTENT",),
            )
        if intent.intent_type == IntentType.CONFIRM_REQUEST:
            return self._validate_confirmation(intent)
        if intent.intent_type != IntentType.TRANSFER_SHIFT:
            return ValidationDecision(state=RequestState.REJECTED, reason_codes=("UNSUPPORTED_INTENT",))

        from_id, to_id, shift_id = intent.from_worker_id, intent.to_worker_id, intent.shift_id
        if from_id not in run.workers or to_id not in run.workers:
            return ValidationDecision(state=RequestState.REJECTED, reason_codes=("WORKER_OUTSIDE_CANDIDATE_SET",))
        if shift_id not in run.shifts:
            return ValidationDecision(state=RequestState.REJECTED, reason_codes=("SHIFT_OUTSIDE_CANDIDATE_SET",))
        shift = run.shifts[shift_id]
        if from_id == to_id:
            return ValidationDecision(state=RequestState.REJECTED, reason_codes=("SAME_WORKER_TRANSFER",))
        if shift.current_owner_id != from_id:
            return ValidationDecision(state=RequestState.REJECTED, reason_codes=("FROM_WORKER_NOT_CURRENT_OWNER",))
        if intent.confirmation != ConfirmationStatus.PRESENT:
            return ValidationDecision(state=RequestState.WAITING_CONFIRMATION, reason_codes=("RECIPIENT_CONFIRMATION_MISSING",))
        if intent.confirmation_by_worker_id != to_id:
            return ValidationDecision(state=RequestState.REJECTED, reason_codes=("CONFIRMATION_WORKER_MISMATCH",))

        target = run.workers[to_id]
        if not any(window.covers(shift.start_at, shift.end_at) for window in target.availability):
            return ValidationDecision(state=RequestState.REJECTED, reason_codes=("TARGET_UNAVAILABLE",))
        for other in run.shifts.values():
            if other.shift_id == shift.shift_id or other.current_owner_id != to_id:
                continue
            overlaps = shift.start_at < other.end_at and other.start_at < shift.end_at
            if overlaps:
                return ValidationDecision(state=RequestState.REJECTED, reason_codes=("TARGET_SHIFT_CONFLICT",))

        if intent.dependency_request_id:
            dependency = self.repository.get_request(intent.dependency_request_id)
            if dependency is None or dependency.state != RequestState.VERIFIED:
                return ValidationDecision(state=RequestState.REJECTED, reason_codes=("DEPENDENCY_NOT_VERIFIED",))
            if dependency.applied_ledger_id != shift.custody_head_id:
                return ValidationDecision(state=RequestState.REJECTED, reason_codes=("DEPENDENCY_NOT_CURRENT_HEAD",))

        return ValidationDecision(
            state=RequestState.READY,
            reason_codes=("ALL_RULES_PASSED",),
            expected_schedule_version=run.schedule_version,
            expected_shift_version=shift.version,
            expected_custody_head_id=shift.custody_head_id,
        )

    def _validate_confirmation(self, intent: StructuredIntent) -> ValidationDecision:
        target = self.repository.get_request(intent.target_request_id or "")
        if target is None:
            return ValidationDecision(state=RequestState.REJECTED, reason_codes=("TARGET_REQUEST_NOT_FOUND",))
        if target.state != RequestState.WAITING_CONFIRMATION:
            return ValidationDecision(state=RequestState.REJECTED, reason_codes=("TARGET_REQUEST_NOT_WAITING",))
        if target.intent is None or target.intent.to_worker_id != intent.confirmation_by_worker_id:
            return ValidationDecision(state=RequestState.REJECTED, reason_codes=("CONFIRMER_NOT_TARGET_WORKER",))
        if intent.decision != ConfirmationDecision.ACCEPT:
            return ValidationDecision(state=RequestState.REJECTED, reason_codes=("CONFIRMATION_NOT_ACCEPTED",))
        return ValidationDecision(state=RequestState.READY, reason_codes=("CONFIRMATION_RULE_PASSED",))

    def verify_outcome(self, request: RequestRecord, ledger_id: str) -> ProcessingResult:
        """Independent read-back after APPLIED; only this path can produce VERIFIED."""
        run = self.repository.get_run(request.run_id)
        ledger = self.repository.get_ledger_event(ledger_id)
        intent = request.intent
        if run is None or ledger is None or intent is None or intent.shift_id not in run.shifts:
            request.state = RequestState.FAILED
            request.reason_codes = ("VERIFY_READBACK_MISSING",)
            self.repository.save_request(request)
            return self._result(request)
        shift = run.shifts[intent.shift_id]
        checks = {
            "owner_matches": shift.current_owner_id == intent.to_worker_id,
            "head_matches": shift.custody_head_id == ledger_id,
            "shift_version_matches": shift.version == ledger.shift_version,
            "schedule_version_matches": run.schedule_version == ledger.schedule_version,
            "request_matches": ledger.request_id == request.request_id,
            "predecessor_present": ledger.predecessor_id is not None,
        }
        if not all(checks.values()):
            request.state = RequestState.FAILED
            request.reason_codes = tuple(name for name, passed in checks.items() if not passed)
            self.repository.save_request(request)
            return self._result(request)

        record = VerificationRecord(
            verification_id=f"verify:{request.request_id}",
            request_id=request.request_id,
            ledger_id=ledger_id,
            verified_at=self._now(),
            checks=tuple(checks),
        )
        self.repository.save_verification(record)
        request.state = RequestState.VERIFIED
        request.reason_codes = ("READBACK_VERIFIED",)
        self.repository.save_request(request)
        log_event(
            LOGGER,
            "readback_verified",
            request_id=request.request_id,
            ledger_id=ledger_id,
            state=request.state.value,
        )
        return self._result(request)

    @staticmethod
    def _result(request: RequestRecord) -> ProcessingResult:
        return ProcessingResult(
            source_event_id=request.source_event_id,
            request_id=request.request_id,
            state=request.state,
            reason_codes=request.reason_codes,
            ledger_id=request.applied_ledger_id,
        )

    @staticmethod
    def _reject_unstored(event, reason: str) -> ProcessingResult:
        return ProcessingResult(
            source_event_id=event.event_id,
            request_id=event.request_id,
            state=RequestState.REJECTED,
            reason_codes=(reason,),
        )
