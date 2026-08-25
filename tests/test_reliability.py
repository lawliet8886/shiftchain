from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock

import pytest

from shiftchain.cloud_config import CloudConfig
from shiftchain.cloud_workflow import (
    CloudWorkflow,
    IntegrityVerificationError,
    LostAcknowledgementAfterVerify,
)
from shiftchain.engine import ReconciliationEngine
from shiftchain.frozen_data import frozen_repository, intent_for
from shiftchain.models import ConfirmationStatus, RequestRecord, RequestState, TransferCommit
from shiftchain.reliability import LOST_ACK_AFTER_VERIFY_ONCE, NoOpVerificationResult
from shiftchain.tasks import ResumePayload


def config() -> CloudConfig:
    return CloudConfig(
        project_id="gen-lang-client-0643751280",
        region="us-central1",
        firestore_database="shiftchain",
        queue_name="shiftchain-resume",
        task_caller_email="caller@example.iam.gserviceaccount.com",
        service_base_url="https://shiftchain.example.run.app",
        task_audience="https://shiftchain.example.run.app",
        demo_delay_seconds=15,
    )


class FaultStore:
    def __init__(self) -> None:
        self.lock = Lock()
        self.mode = "DEMO"
        self.injection = None
        self.used = False
        self.telemetry = None


class ReliabilityRepositoryStub:
    def __init__(self, store: FaultStore | None = None) -> None:
        self.inner = frozen_repository()
        ReconciliationEngine(self.inner).process("EVT-003", intent_for("EVT-003"))
        self.store = store or FaultStore()
        self.integrity_ok = True
        self.noop_ids: set[str] = set()
        self.readback_calls = 0
        self.metadata = {
            "request_id": "REQ-003",
            "workflow_status": RequestState.WAITING_CONFIRMATION.value,
            "resume_generation": 2,
            "confirmation_evidence": {"confirmed_by_worker_id": "W-005"},
            "idempotency_key": "request:RUN-DEMO-001:REQ-003",
            "activity": [],
        }

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def event_metadata(self, event_id: str):
        request = self.inner.get_request("REQ-003")
        self.metadata["workflow_status"] = request.state.value
        self.metadata["applied_ledger_id"] = request.applied_ledger_id
        return self.metadata

    def record_resume_activity(self, event_id: str, **entry) -> None:
        self.metadata["activity"].append(entry)

    def configure_failure_injection(self, injection: str) -> bool:
        if injection != LOST_ACK_AFTER_VERIFY_ONCE:
            raise ValueError("unsupported")
        with self.store.lock:
            if self.store.mode != "DEMO":
                return False
            self.store.injection = injection
            self.store.used = False
            return True

    def consume_failure_injection(self, event_id: str, **telemetry) -> bool:
        with self.store.lock:
            request = self.inner.get_request("REQ-003")
            if (
                self.store.mode != "DEMO"
                or self.store.injection != LOST_ACK_AFTER_VERIFY_ONCE
                or self.store.used
                or request.state != RequestState.VERIFIED
                or self.inner.get_verification("REQ-003") is None
            ):
                return False
            self.store.used = True
            self.store.telemetry = telemetry
            return True

    def verify_existing_effect(self, event_id: str, *, resume_generation: int, **kwargs) -> NoOpVerificationResult:
        self.readback_calls += 1
        run = self.inner.get_run("RUN-DEMO-001")
        request = self.inner.get_request("REQ-003")
        shift = run.shifts["SHF-260827-M"]
        chain = self.inner.custody_chain("SHF-260827-M")
        valid = (
            self.integrity_ok
            and request.state == RequestState.VERIFIED
            and self.inner.get_verification("REQ-003") is not None
            and shift.current_owner_id == "W-005"
            and shift.version == 1
            and run.schedule_version == 1
            and [entry.to_worker_id for entry in chain] == ["W-004", "W-005"]
        )
        if not valid:
            return NoOpVerificationResult(False, None, ("INTEGRITY_MISMATCH",))
        evidence_id = f"noop:{event_id}:g{resume_generation}"
        self.noop_ids.add(evidence_id)
        return NoOpVerificationResult(
            True,
            evidence_id,
            (),
            shift.current_owner_id,
            shift.version,
            run.schedule_version,
            shift.custody_head_id,
        )

    def prepare_applied(self) -> None:
        event = self.inner.get_event("EVT-003")
        run = self.inner.get_run("RUN-DEMO-001")
        intent = intent_for("EVT-003").model_copy(
            update={"confirmation": ConfirmationStatus.PRESENT, "confirmation_by_worker_id": "W-005"}
        )
        request = RequestRecord(
            request_id="REQ-003",
            source_event_id="EVT-003",
            run_id="RUN-DEMO-001",
            state=RequestState.READY,
            intent=intent,
        )
        self.inner.save_request(request)
        shift = run.shifts["SHF-260827-M"]
        commit = self.inner.commit_transfer(
            TransferCommit(
                run_id=run.run_id,
                request_id=request.request_id,
                source_event_id=event.event_id,
                shift_id=shift.shift_id,
                from_worker_id="W-004",
                to_worker_id="W-005",
                expected_schedule_version=0,
                expected_shift_version=0,
                expected_custody_head_id=shift.custody_head_id,
                occurred_at=event.occurred_at,
            )
        )
        assert commit.applied


def workflow(repository: ReliabilityRepositoryStub) -> CloudWorkflow:
    result = CloudWorkflow(config=config(), client=None, scheduler=None)
    result.repository = lambda run_id: repository
    return result


def payload() -> ResumePayload:
    return ResumePayload(run_id="RUN-DEMO-001", target_event_id="EVT-003", resume_generation=2)


def apply_with_injected_lost_ack(repository: ReliabilityRepositoryStub) -> None:
    assert repository.configure_failure_injection(LOST_ACK_AFTER_VERIFY_ONCE)
    with pytest.raises(LostAcknowledgementAfterVerify):
        workflow(repository).resume(payload(), task_name="g2", task_attempt="0")


def test_failure_injection_disabled_by_default() -> None:
    repository = ReliabilityRepositoryStub()
    assert workflow(repository).resume(payload(), task_name="g2", task_attempt="0")[0] == 200
    assert repository.store.used is False


def test_injection_only_allowed_in_demo_mode() -> None:
    repository = ReliabilityRepositoryStub()
    repository.store.mode = "PRODUCTION"
    assert repository.configure_failure_injection(LOST_ACK_AFTER_VERIFY_ONCE) is False


def test_injection_is_consumed_only_once() -> None:
    repository = ReliabilityRepositoryStub()
    apply_with_injected_lost_ack(repository)
    assert repository.consume_failure_injection("EVT-003") is False


def test_injection_survives_repository_reload() -> None:
    store = FaultStore()
    first = ReliabilityRepositoryStub(store)
    second = ReliabilityRepositoryStub(store)
    assert first.configure_failure_injection(LOST_ACK_AFTER_VERIFY_ONCE)
    assert second.store.injection == LOST_ACK_AFTER_VERIFY_ONCE


def test_fault_cannot_trigger_twice_under_concurrent_calls() -> None:
    repository = ReliabilityRepositoryStub()
    workflow(repository).resume(payload(), task_name="warm", task_attempt="0")
    repository.configure_failure_injection(LOST_ACK_AFTER_VERIFY_ONCE)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: repository.consume_failure_injection("EVT-003"), range(2)))
    assert sorted(results) == [False, True]


def test_fault_cannot_be_consumed_before_verified() -> None:
    repository = ReliabilityRepositoryStub()
    repository.configure_failure_injection(LOST_ACK_AFTER_VERIFY_ONCE)
    assert repository.consume_failure_injection("EVT-003") is False


def test_503_occurs_only_after_verified() -> None:
    repository = ReliabilityRepositoryStub()
    apply_with_injected_lost_ack(repository)
    assert repository.get_request("REQ-003").state == RequestState.VERIFIED
    assert repository.get_verification("REQ-003") is not None


def test_request_remains_verified_after_injected_503() -> None:
    repository = ReliabilityRepositoryStub()
    apply_with_injected_lost_ack(repository)
    assert repository.get_request("REQ-003").state == RequestState.VERIFIED


def test_injected_503_persists_task_attempt_telemetry() -> None:
    repository = ReliabilityRepositoryStub()
    apply_with_injected_lost_ack(repository)
    assert repository.store.telemetry == {
        "resume_generation": 2,
        "task_name": "g2",
        "task_attempt": "0",
    }


def test_retry_never_instantiates_gemini(monkeypatch) -> None:
    repository = ReliabilityRepositoryStub()
    apply_with_injected_lost_ack(repository)
    monkeypatch.setattr("shiftchain.cloud_workflow.GeminiIntentParser", lambda: (_ for _ in ()).throw(AssertionError("Gemini called")))
    assert workflow(repository).resume(payload(), task_name="g2", task_attempt="1")[0] == 204


def test_verified_retry_performs_readback_and_noop() -> None:
    repository = ReliabilityRepositoryStub()
    apply_with_injected_lost_ack(repository)
    status, result = workflow(repository).resume(payload(), task_name="g2", task_attempt="1")
    assert status == 204 and result["result"] == "NO_OP_VERIFIED"
    assert repository.readback_calls == 1


def test_retry_does_not_increment_versions_or_custody() -> None:
    repository = ReliabilityRepositoryStub()
    apply_with_injected_lost_ack(repository)
    before_run = repository.get_run("RUN-DEMO-001")
    before_chain = repository.custody_chain("SHF-260827-M")
    workflow(repository).resume(payload(), task_name="g2", task_attempt="1")
    after_run = repository.get_run("RUN-DEMO-001")
    after_chain = repository.custody_chain("SHF-260827-M")
    assert before_run == after_run
    assert before_chain == after_chain


def test_retry_does_not_change_custody_head() -> None:
    repository = ReliabilityRepositoryStub()
    apply_with_injected_lost_ack(repository)
    head = repository.get_run("RUN-DEMO-001").shifts["SHF-260827-M"].custody_head_id
    workflow(repository).resume(payload(), task_name="g2", task_attempt="1")
    assert repository.get_run("RUN-DEMO-001").shifts["SHF-260827-M"].custody_head_id == head


def test_duplicate_noop_evidence_is_idempotent() -> None:
    repository = ReliabilityRepositoryStub()
    apply_with_injected_lost_ack(repository)
    workflow(repository).resume(payload(), task_name="g2", task_attempt="1")
    workflow(repository).resume(payload(), task_name="g2", task_attempt="2")
    assert repository.noop_ids == {"noop:EVT-003:g2"}


def test_verified_with_inconsistent_ledger_is_not_successful_noop() -> None:
    repository = ReliabilityRepositoryStub()
    apply_with_injected_lost_ack(repository)
    repository.integrity_ok = False
    with pytest.raises(IntegrityVerificationError):
        workflow(repository).resume(payload(), task_name="g2", task_attempt="1")
    assert not repository.noop_ids


def test_applied_request_is_verified_without_reapplying(monkeypatch) -> None:
    repository = ReliabilityRepositoryStub()
    repository.prepare_applied()
    monkeypatch.setattr(ReconciliationEngine, "process", lambda *_: (_ for _ in ()).throw(AssertionError("reapplied")))
    status, _ = workflow(repository).resume(payload(), task_name="g2", task_attempt="0")
    assert status == 200
    assert repository.get_request("REQ-003").state == RequestState.VERIFIED


def test_normal_run_without_injection_returns_2xx() -> None:
    repository = ReliabilityRepositoryStub()
    status, result = workflow(repository).resume(payload(), task_name="g2", task_attempt="0")
    assert status == 200 and result["result"]["state"] == RequestState.VERIFIED.value


def test_lost_ack_preserves_exactly_one_custody_edge() -> None:
    repository = ReliabilityRepositoryStub()
    apply_with_injected_lost_ack(repository)
    workflow(repository).resume(payload(), task_name="g2", task_attempt="1")
    chain = repository.custody_chain("SHF-260827-M")
    assert [entry.to_worker_id for entry in chain] == ["W-004", "W-005"]


def test_noop_id_is_generation_deterministic() -> None:
    repository = ReliabilityRepositoryStub()
    apply_with_injected_lost_ack(repository)
    _, result = workflow(repository).resume(payload(), task_name="g2", task_attempt="1")
    assert result["evidence_id"] == "noop:EVT-003:g2"
