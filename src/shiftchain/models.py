from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class RequestState(StrEnum):
    RECEIVED = "RECEIVED"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    READY = "READY"
    APPLIED = "APPLIED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class IntentType(StrEnum):
    TRANSFER_SHIFT = "TRANSFER_SHIFT"
    CONFIRM_REQUEST = "CONFIRM_REQUEST"
    UNKNOWN = "UNKNOWN"


class ConfirmationStatus(StrEnum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ConfirmationDecision(StrEnum):
    ACCEPT = "ACCEPT"
    DECLINE = "DECLINE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class LanguageCode(StrEnum):
    EN = "en"
    PT_BR = "pt-BR"
    UNKNOWN = "unknown"


class LedgerEventType(StrEnum):
    INITIAL_ASSIGNMENT = "INITIAL_ASSIGNMENT"
    TRANSFER_APPLIED = "TRANSFER_APPLIED"
    TRANSFER = "TRANSFER_APPLIED"
    TRANSFER_VERIFIED = "TRANSFER_VERIFIED"
    NO_OP_VERIFIED = "NO_OP_VERIFIED"


class Evidence(StrictModel):
    field: str
    quote: str


class StructuredIntent(StrictModel):
    schema_version: str = "1.0"
    source_event_id: str
    intent_type: IntentType
    from_worker_id: str | None
    to_worker_id: str | None
    shift_id: str | None
    target_request_id: str | None
    dependency_request_id: str | None
    confirmation: ConfirmationStatus
    confirmation_by_worker_id: str | None
    decision: ConfirmationDecision
    language: LanguageCode
    ambiguities: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_shape(self) -> StructuredIntent:
        if self.intent_type == IntentType.TRANSFER_SHIFT:
            required = (self.from_worker_id, self.to_worker_id, self.shift_id)
            if not all(required) and not self.ambiguities:
                raise ValueError("transfer intent needs from, to and shift or an ambiguity")
        if self.intent_type == IntentType.CONFIRM_REQUEST:
            if not self.target_request_id or not self.confirmation_by_worker_id:
                raise ValueError("confirmation intent needs target request and confirming worker")
        return self


class AvailabilityWindow(StrictModel):
    start_at: datetime
    end_at: datetime

    def covers(self, start_at: datetime, end_at: datetime) -> bool:
        return self.start_at <= start_at and end_at <= self.end_at


class Worker(StrictModel):
    worker_id: str
    name: str
    role: str
    availability: tuple[AvailabilityWindow, ...]


class Shift(StrictModel):
    shift_id: str
    label: str
    start_at: datetime
    end_at: datetime
    original_owner_id: str
    current_owner_id: str
    version: int = 0
    custody_head_id: str


class ScheduleRun(StrictModel):
    run_id: str
    organization: str
    period_start: datetime
    period_end: datetime
    schedule_version: int = 0
    authorized: bool = True
    expires_at: datetime
    workers: dict[str, Worker]
    shifts: dict[str, Shift]


class SourceEvent(StrictModel):
    event_id: str
    request_id: str
    run_id: str
    occurred_at: datetime
    message: str


class RequestRecord(StrictModel):
    request_id: str
    source_event_id: str
    run_id: str
    state: RequestState = RequestState.RECEIVED
    intent: StructuredIntent | None = None
    reason_codes: tuple[str, ...] = ()
    applied_ledger_id: str | None = None
    expected_schedule_version: int | None = None
    expected_shift_version: int | None = None


class CustodyLedgerEvent(StrictModel):
    ledger_id: str
    event_type: LedgerEventType
    run_id: str
    shift_id: str
    request_id: str | None
    source_event_id: str | None
    from_worker_id: str | None
    to_worker_id: str
    predecessor_id: str | None
    shift_version: int
    schedule_version: int
    occurred_at: datetime


class VerificationRecord(StrictModel):
    verification_id: str
    request_id: str
    ledger_id: str
    verified_at: datetime
    checks: tuple[str, ...]


class CandidateContext(StrictModel):
    source_event: SourceEvent
    worker_candidates: dict[str, str]
    shift_candidates: dict[str, str]
    request_candidates: dict[str, str]

    def prompt_payload(self) -> dict[str, Any]:
        return {
            "source_event_id": self.source_event.event_id,
            "message": self.source_event.message,
            "worker_candidates": self.worker_candidates,
            "shift_candidates": self.shift_candidates,
            "request_candidates": self.request_candidates,
        }


class ValidationDecision(StrictModel):
    state: RequestState
    reason_codes: tuple[str, ...]
    expected_schedule_version: int | None = None
    expected_shift_version: int | None = None
    expected_custody_head_id: str | None = None


class TransferCommit(StrictModel):
    run_id: str
    request_id: str
    source_event_id: str
    shift_id: str
    from_worker_id: str
    to_worker_id: str
    expected_schedule_version: int
    expected_shift_version: int
    expected_custody_head_id: str
    occurred_at: datetime


class CommitResult(StrictModel):
    applied: bool
    idempotent: bool
    conflict_code: str | None = None
    ledger_event: CustodyLedgerEvent | None = None


class ProcessingResult(StrictModel):
    source_event_id: str
    request_id: str
    state: RequestState
    reason_codes: tuple[str, ...]
    idempotent: bool = False
    ledger_id: str | None = None
