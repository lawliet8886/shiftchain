from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from shiftchain.models import (
    AvailabilityWindow,
    CandidateContext,
    ConfirmationDecision,
    ConfirmationStatus,
    Evidence,
    IntentType,
    LanguageCode,
    ScheduleRun,
    Shift,
    SourceEvent,
    StructuredIntent,
    Worker,
)
from shiftchain.repository import InMemoryRepository, initial_ledger_for

TZ = ZoneInfo("America/New_York")


def dt(day: int, hour: int) -> datetime:
    return datetime(2026, 8, day, hour, tzinfo=TZ)


def window(day: int, start: int, end: int) -> AvailabilityWindow:
    return AvailabilityWindow(start_at=dt(day, start), end_at=dt(day, end))


def frozen_run(*, authorized: bool = True, expired: bool = False) -> ScheduleRun:
    workers = (
        Worker(worker_id="W-001", name="Maya Brooks", role="Community Site Lead", availability=(window(24, 6, 14), window(25, 6, 14), window(26, 6, 14), window(26, 17, 23))),
        Worker(worker_id="W-002", name="Liam Chen", role="Field Coordinator", availability=(window(26, 17, 23), window(27, 17, 23), window(28, 17, 23))),
        Worker(worker_id="W-003", name="Sofia Reyes", role="Program Host", availability=(window(25, 17, 23), window(26, 17, 23), window(27, 17, 23))),
        Worker(worker_id="W-004", name="Noah Patel", role="Logistics Coordinator", availability=(window(27, 6, 14), window(28, 6, 14))),
        Worker(worker_id="W-005", name="Emma Wilson", role="Site Steward", availability=(window(24, 6, 14), window(27, 6, 14), window(28, 6, 14))),
        Worker(worker_id="W-006", name="Lucas Martin", role="Facilities Technician", availability=(window(25, 17, 23), window(28, 17, 23))),
    )
    shifts = (
        Shift(shift_id="SHF-260826-E", label="Harbor Hub Close", start_at=dt(26, 18), end_at=dt(26, 22), original_owner_id="W-001", current_owner_id="W-001", custody_head_id="ledger:initial:SHF-260826-E"),
        Shift(shift_id="SHF-260827-M", label="Supply Point Open", start_at=dt(27, 8), end_at=dt(27, 12), original_owner_id="W-004", current_owner_id="W-004", custody_head_id="ledger:initial:SHF-260827-M"),
        Shift(shift_id="SHF-260828-M", label="Harbor Hub Open", start_at=dt(28, 8), end_at=dt(28, 12), original_owner_id="W-005", current_owner_id="W-005", custody_head_id="ledger:initial:SHF-260828-M"),
        Shift(shift_id="SHF-260828-E", label="Supply Point Close", start_at=dt(28, 18), end_at=dt(28, 22), original_owner_id="W-006", current_owner_id="W-006", custody_head_id="ledger:initial:SHF-260828-E"),
    )
    return ScheduleRun(
        run_id="RUN-DEMO-001",
        organization="Harborlight Community Operations (HCO)",
        period_start=dt(24, 0),
        period_end=dt(30, 23),
        schedule_version=0,
        authorized=authorized,
        expires_at=dt(24, 0) if expired else dt(31, 0),
        workers={worker.worker_id: worker for worker in workers},
        shifts={shift.shift_id: shift for shift in shifts},
    )


def frozen_events() -> tuple[SourceEvent, ...]:
    return (
        SourceEvent(event_id="EVT-001", request_id="REQ-001", run_id="RUN-DEMO-001", occurred_at=dt(25, 9), message="Confirmed handoff: Liam Chen will take Maya Brooks’s Harbor Hub Close shift on Wednesday, Aug 26, 18:00–22:00. We both approve. — Maya & Liam"),
        SourceEvent(event_id="EVT-002", request_id="REQ-002", run_id="RUN-DEMO-001", occurred_at=dt(25, 10), message="Confirmed handoff: Sofia Reyes will take the Wednesday Harbor Hub Close shift I received from Maya. We both approve. — Liam & Sofia"),
        SourceEvent(event_id="EVT-003", request_id="REQ-003", run_id="RUN-DEMO-001", occurred_at=dt(25, 11), message="Please transfer my Supply Point Open shift on Thursday, Aug 27, 08:00–12:00, to Emma Wilson. I approve the handoff; Emma has not confirmed yet. — Noah"),
        SourceEvent(event_id="EVT-004", request_id="REQ-004", run_id="RUN-DEMO-001", occurred_at=dt(25, 12), message="I confirm request REQ-003 and accept Noah Patel’s Supply Point Open shift on Thursday, Aug 27, 08:00–12:00. — Emma"),
        SourceEvent(event_id="AMB-001", request_id="REQ-AMB-001", run_id="RUN-DEMO-001", occurred_at=dt(25, 13), message="Can L. cover my shift on Wednesday?"),
    )


def intent_for(event_id: str) -> StructuredIntent:
    common = {"schema_version": "1.0", "source_event_id": event_id, "language": LanguageCode.EN}
    fixtures = {
        "EVT-001": StructuredIntent(**common, intent_type=IntentType.TRANSFER_SHIFT, from_worker_id="W-001", to_worker_id="W-002", shift_id="SHF-260826-E", target_request_id=None, dependency_request_id=None, confirmation=ConfirmationStatus.PRESENT, confirmation_by_worker_id="W-002", decision=ConfirmationDecision.NOT_APPLICABLE, ambiguities=[], evidence=[Evidence(field="transfer", quote="Liam Chen will take Maya Brooks’s Harbor Hub Close shift"), Evidence(field="confirmation", quote="We both approve")], confidence=0.99),
        "EVT-002": StructuredIntent(**common, intent_type=IntentType.TRANSFER_SHIFT, from_worker_id="W-002", to_worker_id="W-003", shift_id="SHF-260826-E", target_request_id=None, dependency_request_id="REQ-001", confirmation=ConfirmationStatus.PRESENT, confirmation_by_worker_id="W-003", decision=ConfirmationDecision.NOT_APPLICABLE, ambiguities=[], evidence=[Evidence(field="transfer", quote="Sofia Reyes will take the Wednesday Harbor Hub Close shift I received from Maya"), Evidence(field="confirmation", quote="We both approve")], confidence=0.98),
        "EVT-003": StructuredIntent(**common, intent_type=IntentType.TRANSFER_SHIFT, from_worker_id="W-004", to_worker_id="W-005", shift_id="SHF-260827-M", target_request_id=None, dependency_request_id=None, confirmation=ConfirmationStatus.ABSENT, confirmation_by_worker_id=None, decision=ConfirmationDecision.NOT_APPLICABLE, ambiguities=[], evidence=[Evidence(field="transfer", quote="transfer my Supply Point Open shift ... to Emma Wilson"), Evidence(field="confirmation", quote="Emma has not confirmed yet")], confidence=0.99),
        "EVT-004": StructuredIntent(**common, intent_type=IntentType.CONFIRM_REQUEST, from_worker_id=None, to_worker_id=None, shift_id="SHF-260827-M", target_request_id="REQ-003", dependency_request_id=None, confirmation=ConfirmationStatus.PRESENT, confirmation_by_worker_id="W-005", decision=ConfirmationDecision.ACCEPT, ambiguities=[], evidence=[Evidence(field="target", quote="request REQ-003"), Evidence(field="confirmation", quote="I confirm ... and accept")], confidence=0.99),
        "AMB-001": StructuredIntent(**common, intent_type=IntentType.UNKNOWN, from_worker_id=None, to_worker_id=None, shift_id=None, target_request_id=None, dependency_request_id=None, confirmation=ConfirmationStatus.ABSENT, confirmation_by_worker_id=None, decision=ConfirmationDecision.NOT_APPLICABLE, ambiguities=["L. could refer to Liam Chen or Lucas Martin", "sender and exact shift are not identified"], evidence=[Evidence(field="ambiguity", quote="L."), Evidence(field="ambiguity", quote="my shift on Wednesday")], confidence=0.25),
    }
    return fixtures[event_id]


def frozen_repository(*, authorized: bool = True, expired: bool = False) -> InMemoryRepository:
    run = frozen_run(authorized=authorized, expired=expired)
    return InMemoryRepository(run, frozen_events(), initial_ledger_for(run, dt(24, 0)))


def candidate_context(repository: InMemoryRepository, event_id: str) -> CandidateContext:
    event = repository.get_event(event_id)
    run = repository.get_run(event.run_id) if event else None
    if event is None or run is None:
        raise KeyError(event_id)
    requests = {
        "REQ-001": "EVT-001 Maya to Liam",
        "REQ-002": "EVT-002 Liam to Sofia",
        "REQ-003": "EVT-003 Noah to Emma awaiting confirmation",
    }
    shifts = {
        shift_id: f"{shift.label}; {shift.start_at.isoformat()} to {shift.end_at.isoformat()}; current owner {shift.current_owner_id}"
        for shift_id, shift in run.shifts.items()
    }
    if event_id == "AMB-001":
        # Parser-only adversarial candidate; it is never persisted into the frozen run.
        shifts["AMB-SHF-WED-M"] = "Candidate responsibility; Wednesday morning; owner not established by message"
    return CandidateContext(
        source_event=event,
        worker_candidates={worker_id: f"{worker.name}; {worker.role}" for worker_id, worker in run.workers.items()},
        shift_candidates=shifts,
        request_candidates=requests,
    )
