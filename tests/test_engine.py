from datetime import datetime, timezone

from shiftchain.engine import ReconciliationEngine
from shiftchain.frozen_data import frozen_repository, intent_for
from shiftchain.models import RequestState, TransferCommit


def test_a_valid_direct_transfer_maya_to_liam() -> None:
    repository = frozen_repository()
    result = ReconciliationEngine(repository).process("EVT-001", intent_for("EVT-001"))
    run = repository.get_run("RUN-DEMO-001")
    assert result.state == RequestState.VERIFIED
    assert run is not None
    assert run.shifts["SHF-260826-E"].current_owner_id == "W-002"
    assert run.shifts["SHF-260826-E"].version == 1
    assert run.schedule_version == 1


def test_b_valid_chained_transfer_reconstructs_custody() -> None:
    repository = frozen_repository()
    engine = ReconciliationEngine(repository)
    assert engine.process("EVT-001", intent_for("EVT-001")).state == RequestState.VERIFIED
    assert engine.process("EVT-002", intent_for("EVT-002")).state == RequestState.VERIFIED
    chain = repository.custody_chain("SHF-260826-E")
    assert [entry.to_worker_id for entry in chain] == ["W-001", "W-002", "W-003"]
    assert chain[2].predecessor_id == chain[1].ledger_id
    run = repository.get_run("RUN-DEMO-001")
    assert run is not None and run.shifts["SHF-260826-E"].current_owner_id == "W-003"


def test_c_idempotent_replay_does_not_increment_versions() -> None:
    repository = frozen_repository()
    engine = ReconciliationEngine(repository)
    first = engine.process("EVT-001", intent_for("EVT-001"))
    before = repository.get_run("RUN-DEMO-001")
    replay = engine.process("EVT-001", intent_for("EVT-001"))
    after = repository.get_run("RUN-DEMO-001")
    assert first.state == replay.state == RequestState.VERIFIED
    assert replay.idempotent is True
    assert before == after
    assert len(repository.custody_chain("SHF-260826-E")) == 2


def test_d_invalid_original_owner_transfer_after_chain_fails() -> None:
    repository = frozen_repository()
    engine = ReconciliationEngine(repository)
    engine.process("EVT-001", intent_for("EVT-001"))
    engine.process("EVT-002", intent_for("EVT-002"))
    invalid = intent_for("EVT-003").model_copy(
        update={
            "from_worker_id": "W-001",
            "to_worker_id": "W-003",
            "shift_id": "SHF-260826-E",
            "confirmation": "PRESENT",
            "confirmation_by_worker_id": "W-003",
        }
    )
    result = engine.process("EVT-003", invalid)
    assert result.state == RequestState.REJECTED
    assert result.reason_codes == ("FROM_WORKER_NOT_CURRENT_OWNER",)


def test_e_expired_and_unauthorized_runs_fail_closed() -> None:
    expired = ReconciliationEngine(frozen_repository(expired=True), now=lambda: datetime(2026, 8, 25, tzinfo=timezone.utc))
    unauthorized = ReconciliationEngine(frozen_repository(authorized=False))
    assert expired.process("EVT-001", intent_for("EVT-001")).reason_codes == ("RUN_EXPIRED",)
    assert unauthorized.process("EVT-001", intent_for("EVT-001")).reason_codes == ("RUN_UNAUTHORIZED",)


def test_missing_recipient_confirmation_waits_without_mutation() -> None:
    repository = frozen_repository()
    before = repository.get_run("RUN-DEMO-001")
    result = ReconciliationEngine(repository).process("EVT-003", intent_for("EVT-003"))
    after = repository.get_run("RUN-DEMO-001")
    assert result.state == RequestState.WAITING_CONFIRMATION
    assert before == after


def test_confirmation_event_validates_but_does_not_resume_in_phase_1() -> None:
    repository = frozen_repository()
    engine = ReconciliationEngine(repository)
    engine.process("EVT-003", intent_for("EVT-003"))
    result = engine.process("EVT-004", intent_for("EVT-004"))
    target = repository.get_request("REQ-003")
    assert result.state == RequestState.VERIFIED
    assert target is not None and target.state == RequestState.WAITING_CONFIRMATION


def test_ambiguous_message_never_mutates_state() -> None:
    repository = frozen_repository()
    before = repository.get_run("RUN-DEMO-001")
    result = ReconciliationEngine(repository).process("AMB-001", intent_for("AMB-001"))
    assert result.state == RequestState.NEEDS_CLARIFICATION
    assert repository.get_run("RUN-DEMO-001") == before


def test_applied_and_verified_are_distinct_transitions() -> None:
    repository = frozen_repository()
    engine = ReconciliationEngine(repository)
    event = repository.get_event("EVT-001")
    run = repository.get_run("RUN-DEMO-001")
    assert event is not None and run is not None
    intent = intent_for("EVT-001")
    from shiftchain.models import RequestRecord

    request = RequestRecord(request_id=event.request_id, source_event_id=event.event_id, run_id=event.run_id, state=RequestState.READY, intent=intent)
    repository.save_request(request)
    shift = run.shifts[intent.shift_id]
    commit = repository.commit_transfer(
        TransferCommit(
            run_id=run.run_id,
            request_id=request.request_id,
            source_event_id=event.event_id,
            shift_id=shift.shift_id,
            from_worker_id="W-001",
            to_worker_id="W-002",
            expected_schedule_version=0,
            expected_shift_version=0,
            expected_custody_head_id=shift.custody_head_id,
            occurred_at=event.occurred_at,
        )
    )
    applied = repository.get_request("REQ-001")
    assert applied is not None and applied.state == RequestState.APPLIED
    assert repository.get_verification("REQ-001") is None
    verified = engine.verify_outcome(applied, commit.ledger_event.ledger_id)
    assert verified.state == RequestState.VERIFIED
    assert repository.get_verification("REQ-001") is not None


def test_stale_compare_and_swap_is_rejected() -> None:
    repository = frozen_repository()
    engine = ReconciliationEngine(repository)
    engine.process("EVT-001", intent_for("EVT-001"))
    event = repository.get_event("EVT-002")
    from shiftchain.models import RequestRecord

    intent = intent_for("EVT-002")
    repository.save_request(RequestRecord(request_id="REQ-STALE", source_event_id=event.event_id, run_id=event.run_id, state=RequestState.READY, intent=intent))
    result = repository.commit_transfer(
        TransferCommit(run_id=event.run_id, request_id="REQ-STALE", source_event_id=event.event_id, shift_id="SHF-260826-E", from_worker_id="W-002", to_worker_id="W-003", expected_schedule_version=0, expected_shift_version=0, expected_custody_head_id="ledger:initial:SHF-260826-E", occurred_at=event.occurred_at)
    )
    assert result.applied is False
    assert result.conflict_code == "SCHEDULE_VERSION_CONFLICT"

