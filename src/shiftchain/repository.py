from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime
from threading import RLock

from shiftchain.models import (
    CommitResult,
    CustodyLedgerEvent,
    LedgerEventType,
    RequestRecord,
    RequestState,
    ScheduleRun,
    SourceEvent,
    TransferCommit,
    VerificationRecord,
)


class ShiftChainRepository(ABC):
    """Storage contract. Phase 1 implements only an in-memory adapter."""

    @abstractmethod
    def get_run(self, run_id: str) -> ScheduleRun | None: ...

    @abstractmethod
    def get_event(self, event_id: str) -> SourceEvent | None: ...

    @abstractmethod
    def get_request(self, request_id: str) -> RequestRecord | None: ...

    @abstractmethod
    def save_request(self, request: RequestRecord) -> None: ...

    @abstractmethod
    def commit_transfer(self, command: TransferCommit) -> CommitResult: ...

    @abstractmethod
    def get_ledger_event(self, ledger_id: str) -> CustodyLedgerEvent | None: ...

    @abstractmethod
    def custody_chain(self, shift_id: str) -> tuple[CustodyLedgerEvent, ...]: ...

    @abstractmethod
    def save_verification(self, record: VerificationRecord) -> None: ...

    @abstractmethod
    def get_verification(self, request_id: str) -> VerificationRecord | None: ...


class InMemoryRepository(ShiftChainRepository):
    def __init__(
        self,
        run: ScheduleRun,
        events: tuple[SourceEvent, ...],
        initial_ledger: tuple[CustodyLedgerEvent, ...],
    ) -> None:
        self._lock = RLock()
        self._runs = {run.run_id: deepcopy(run)}
        self._events = {event.event_id: deepcopy(event) for event in events}
        self._requests: dict[str, RequestRecord] = {}
        self._ledger = {entry.ledger_id: deepcopy(entry) for entry in initial_ledger}
        self._verifications: dict[str, VerificationRecord] = {}

    def get_run(self, run_id: str) -> ScheduleRun | None:
        with self._lock:
            run = self._runs.get(run_id)
            return deepcopy(run) if run else None

    def get_event(self, event_id: str) -> SourceEvent | None:
        with self._lock:
            event = self._events.get(event_id)
            return deepcopy(event) if event else None

    def get_request(self, request_id: str) -> RequestRecord | None:
        with self._lock:
            request = self._requests.get(request_id)
            return deepcopy(request) if request else None

    def save_request(self, request: RequestRecord) -> None:
        with self._lock:
            self._requests[request.request_id] = deepcopy(request)

    def commit_transfer(self, command: TransferCommit) -> CommitResult:
        """Atomic compare-and-swap. Domain eligibility is checked by the engine."""
        with self._lock:
            request = self._requests.get(command.request_id)
            if request and request.applied_ledger_id:
                prior = self._ledger[request.applied_ledger_id]
                return CommitResult(applied=False, idempotent=True, ledger_event=prior)

            run = self._runs.get(command.run_id)
            if run is None:
                return CommitResult(applied=False, idempotent=False, conflict_code="RUN_NOT_FOUND")
            shift = run.shifts.get(command.shift_id)
            if shift is None:
                return CommitResult(applied=False, idempotent=False, conflict_code="SHIFT_NOT_FOUND")
            comparisons = (
                (run.schedule_version == command.expected_schedule_version, "SCHEDULE_VERSION_CONFLICT"),
                (shift.version == command.expected_shift_version, "SHIFT_VERSION_CONFLICT"),
                (shift.custody_head_id == command.expected_custody_head_id, "CUSTODY_HEAD_CONFLICT"),
                (shift.current_owner_id == command.from_worker_id, "CURRENT_OWNER_CONFLICT"),
            )
            for passed, code in comparisons:
                if not passed:
                    return CommitResult(applied=False, idempotent=False, conflict_code=code)

            new_shift_version = shift.version + 1
            new_schedule_version = run.schedule_version + 1
            ledger_id = f"ledger:{command.request_id}:v{new_shift_version}"
            entry = CustodyLedgerEvent(
                ledger_id=ledger_id,
                event_type=LedgerEventType.TRANSFER,
                run_id=command.run_id,
                shift_id=command.shift_id,
                request_id=command.request_id,
                source_event_id=command.source_event_id,
                from_worker_id=command.from_worker_id,
                to_worker_id=command.to_worker_id,
                predecessor_id=shift.custody_head_id,
                shift_version=new_shift_version,
                schedule_version=new_schedule_version,
                occurred_at=command.occurred_at,
            )
            self._ledger[ledger_id] = entry
            shift.current_owner_id = command.to_worker_id
            shift.version = new_shift_version
            shift.custody_head_id = ledger_id
            run.schedule_version = new_schedule_version
            if request is None:
                raise RuntimeError("request must be saved before commit")
            request.state = RequestState.APPLIED
            request.applied_ledger_id = ledger_id
            self._requests[request.request_id] = request
            return CommitResult(applied=True, idempotent=False, ledger_event=entry)

    def get_ledger_event(self, ledger_id: str) -> CustodyLedgerEvent | None:
        with self._lock:
            entry = self._ledger.get(ledger_id)
            return deepcopy(entry) if entry else None

    def custody_chain(self, shift_id: str) -> tuple[CustodyLedgerEvent, ...]:
        with self._lock:
            matching_runs = [run for run in self._runs.values() if shift_id in run.shifts]
            if not matching_runs:
                return ()
            cursor = matching_runs[0].shifts[shift_id].custody_head_id
            reverse_chain: list[CustodyLedgerEvent] = []
            seen: set[str] = set()
            while cursor:
                if cursor in seen:
                    raise RuntimeError("custody ledger cycle detected")
                seen.add(cursor)
                entry = self._ledger[cursor]
                reverse_chain.append(deepcopy(entry))
                cursor = entry.predecessor_id
            return tuple(reversed(reverse_chain))

    def save_verification(self, record: VerificationRecord) -> None:
        with self._lock:
            self._verifications.setdefault(record.request_id, deepcopy(record))

    def get_verification(self, request_id: str) -> VerificationRecord | None:
        with self._lock:
            record = self._verifications.get(request_id)
            return deepcopy(record) if record else None


def initial_ledger_for(run: ScheduleRun, occurred_at: datetime) -> tuple[CustodyLedgerEvent, ...]:
    entries = []
    for shift in run.shifts.values():
        entries.append(
            CustodyLedgerEvent(
                ledger_id=shift.custody_head_id,
                event_type=LedgerEventType.INITIAL_ASSIGNMENT,
                run_id=run.run_id,
                shift_id=shift.shift_id,
                request_id=None,
                source_event_id=None,
                from_worker_id=None,
                to_worker_id=shift.original_owner_id,
                predecessor_id=None,
                shift_version=0,
                schedule_version=0,
                occurred_at=occurred_at,
            )
        )
    return tuple(entries)

