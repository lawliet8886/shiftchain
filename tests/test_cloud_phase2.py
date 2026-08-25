from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from google.auth.exceptions import GoogleAuthError
from pydantic import ValidationError

from shiftchain.cloud_config import CloudConfig
from shiftchain.cloud_workflow import CloudWorkflow, FutureGenerationError
from shiftchain.engine import ReconciliationEngine
from shiftchain.frozen_data import frozen_repository, intent_for
from shiftchain.models import RequestState
from shiftchain.oidc import OIDCAuthenticationError, OIDCAuthorizationError, OIDCValidator
from shiftchain.reliability import NoOpVerificationResult
from shiftchain.tasks import CloudTaskScheduler, ResumePayload, ScheduledTask, task_id_for
from shiftchain import web


def cloud_config() -> CloudConfig:
    return CloudConfig(
        project_id="gen-lang-client-0643751280",
        region="us-central1",
        firestore_database="shiftchain",
        queue_name="shiftchain-resume",
        task_caller_email="shiftchain-task-caller@example.iam.gserviceaccount.com",
        service_base_url="https://shiftchain.example.run.app",
        task_audience="https://shiftchain.example.run.app",
        demo_delay_seconds=15,
    )


def test_resume_payload_is_minimal_and_forbids_unknown_fields() -> None:
    payload = ResumePayload(run_id="RUN-DEMO-001", target_event_id="EVT-003", resume_generation=1)
    assert set(payload.model_dump()) == {"v", "run_id", "target_event_id", "resume_generation", "reason"}
    with pytest.raises(ValidationError):
        ResumePayload(run_id="R", target_event_id="E", resume_generation=1, secret="no")


def test_task_id_is_deterministic_and_generation_scoped() -> None:
    first = ResumePayload(run_id="RUN-DEMO-001", target_event_id="EVT-003", resume_generation=1)
    same = first.model_copy()
    next_generation = first.model_copy(update={"resume_generation": 2})
    assert task_id_for(first) == task_id_for(same)
    assert task_id_for(first) != task_id_for(next_generation)


class FakeTasksClient:
    def __init__(self) -> None:
        self.created = None

    @staticmethod
    def queue_path(project: str, region: str, queue: str) -> str:
        return f"projects/{project}/locations/{region}/queues/{queue}"

    @staticmethod
    def task_path(project: str, region: str, queue: str, task: str) -> str:
        return f"projects/{project}/locations/{region}/queues/{queue}/tasks/{task}"

    def create_task(self, *, parent, task):
        self.created = (parent, task)


def test_cloud_task_has_exact_oidc_identity_audience_and_internal_url() -> None:
    fake = FakeTasksClient()
    scheduler = CloudTaskScheduler(cloud_config(), client=fake)
    payload = ResumePayload(run_id="RUN-DEMO-001", target_event_id="EVT-003", resume_generation=1)
    scheduled = scheduler.create(payload, delay_seconds=15)
    parent, task = fake.created
    assert parent.endswith("/locations/us-central1/queues/shiftchain-resume")
    assert scheduled.name == task.name
    assert task.http_request.url == "https://shiftchain.example.run.app/internal/tasks/resume"
    assert task.http_request.oidc_token.audience == "https://shiftchain.example.run.app"
    assert task.http_request.oidc_token.service_account_email == cloud_config().task_caller_email
    assert b'"resume_generation":1' in task.http_request.body


def test_oidc_accepts_google_claims_for_expected_task_identity() -> None:
    validator = OIDCValidator(
        audience="https://shiftchain.example.run.app",
        expected_email="caller@example.iam.gserviceaccount.com",
        verifier=lambda token, request, audience: {
            "iss": "https://accounts.google.com",
            "aud": audience,
            "exp": 4_102_444_800,
            "email": "caller@example.iam.gserviceaccount.com",
            "email_verified": True,
        },
    )
    assert validator.validate("Bearer signed-token")["email_verified"] is True


@pytest.mark.parametrize("header", [None, "", "Basic abc", "Bearer"])
def test_oidc_rejects_missing_or_malformed_bearer(header) -> None:
    with pytest.raises(OIDCAuthenticationError):
        OIDCValidator("aud", "caller", verifier=lambda *_: {}).validate(header)


def test_oidc_maps_bad_signature_or_audience_to_401() -> None:
    def reject(*_):
        raise GoogleAuthError("signature/audience mismatch")

    with pytest.raises(OIDCAuthenticationError):
        OIDCValidator("aud", "caller", verifier=reject).validate("Bearer token")


def test_oidc_maps_valid_wrong_identity_to_403() -> None:
    claims = {"iss": "accounts.google.com", "email": "other@example.com", "email_verified": True}
    with pytest.raises(OIDCAuthorizationError):
        OIDCValidator("aud", "caller@example.com", verifier=lambda *_: claims).validate("Bearer token")


class ResumeRepository:
    def __init__(self, *, confirmed: bool = True) -> None:
        self.inner = frozen_repository()
        ReconciliationEngine(self.inner).process("EVT-003", intent_for("EVT-003"))
        self.metadata = {
            "request_id": "REQ-003",
            "workflow_status": RequestState.WAITING_CONFIRMATION.value,
            "resume_generation": 1,
            "confirmation_evidence": {"confirmed_by_worker_id": "W-005"} if confirmed else None,
            "idempotency_key": "request:RUN-DEMO-001:REQ-003",
            "activity": [],
        }

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def event_metadata(self, event_id: str):
        assert event_id == "EVT-003"
        request = self.inner.get_request("REQ-003")
        self.metadata["workflow_status"] = request.state.value
        return self.metadata

    def record_resume_activity(self, event_id: str, **entry) -> None:
        assert event_id == "EVT-003"
        self.metadata["activity"].append(entry)
        self.metadata["last_result"] = entry["result"]

    def consume_failure_injection(self, event_id: str, **kwargs) -> bool:
        return False

    def verify_existing_effect(self, event_id: str, **kwargs) -> NoOpVerificationResult:
        run = self.get_run("RUN-DEMO-001")
        shift = run.shifts["SHF-260827-M"]
        return NoOpVerificationResult(
            True,
            f"noop:{event_id}:g{kwargs['resume_generation']}",
            (),
            shift.current_owner_id,
            shift.version,
            run.schedule_version,
            shift.custody_head_id,
        )


def workflow_with(repository: ResumeRepository) -> CloudWorkflow:
    workflow = CloudWorkflow(config=cloud_config(), client=None, scheduler=None)
    workflow.repository = lambda run_id: repository
    return workflow


def test_resume_rehydrates_checkpoint_and_reaches_verified_without_parser(monkeypatch) -> None:
    repository = ResumeRepository()
    monkeypatch.setattr("shiftchain.cloud_workflow.GeminiIntentParser", lambda: (_ for _ in ()).throw(AssertionError("Gemini called")))
    status, result = workflow_with(repository).resume(
        ResumePayload(run_id="RUN-DEMO-001", target_event_id="EVT-003", resume_generation=1),
        task_name="task-1",
        task_attempt="0",
    )
    run = repository.get_run("RUN-DEMO-001")
    assert status == 200
    assert result["result"]["state"] == RequestState.VERIFIED.value
    assert run.shifts["SHF-260827-M"].current_owner_id == "W-005"
    assert run.shifts["SHF-260827-M"].version == 1
    assert run.schedule_version == 1


def test_resume_generation_rules_are_safe_no_ops_or_conflict() -> None:
    repository = ResumeRepository()
    workflow = workflow_with(repository)
    stale = ResumePayload(run_id="RUN-DEMO-001", target_event_id="EVT-003", resume_generation=0)
    status, result = workflow.resume(stale, task_name=None, task_attempt=None)
    assert status == 204 and result["result"] == "STALE_GENERATION_NO_OP"
    future = stale.model_copy(update={"resume_generation": 2})
    with pytest.raises(FutureGenerationError):
        workflow.resume(future, task_name=None, task_attempt=None)


def test_early_wake_is_recorded_and_keeps_waiting_without_mutation() -> None:
    repository = ResumeRepository(confirmed=False)
    before = repository.get_run("RUN-DEMO-001")
    status, result = workflow_with(repository).resume(
        ResumePayload(run_id="RUN-DEMO-001", target_event_id="EVT-003", resume_generation=1),
        task_name="g1",
        task_attempt="0",
    )
    assert status == 204 and result["result"] == "STILL_WAITING_CONFIRMATION"
    assert repository.get_request("REQ-003").state == RequestState.WAITING_CONFIRMATION
    assert repository.get_run("RUN-DEMO-001") == before
    assert repository.metadata["last_result"] == "WAIT_CONDITION_NOT_MET"


class RecoveryRepository(ResumeRepository):
    def __init__(self) -> None:
        super().__init__(confirmed=False)

    def record_confirmation_and_schedule(
        self,
        confirmation_event_id,
        target_request_id,
        confirmer_worker_id,
        evidence,
        *,
        expected_generation,
        resume_generation,
        task_name,
        schedule_at,
    ):
        if self.metadata.get("confirmation_evidence"):
            return "CONFIRMATION_ALREADY_RECORDED"
        assert expected_generation == self.metadata["resume_generation"]
        self.metadata.update(
            confirmation_evidence={"confirmed_by_worker_id": confirmer_worker_id},
            resume_generation=resume_generation,
            scheduled_task_name=task_name,
            next_attempt_at=schedule_at,
            last_result="CONFIRMATION_RECORDED_RESUME_SCHEDULED",
        )
        return "CONFIRMATION_RECORDED_RESUME_SCHEDULED"


class RecoveryScheduler:
    def __init__(self) -> None:
        self.created: list[tuple[ResumePayload, int | None]] = []

    def create(self, payload, delay_seconds=None):
        self.created.append((payload, delay_seconds))
        return ScheduledTask(
            name=f"tasks/{task_id_for(payload)}",
            schedule_at=datetime.now(timezone.utc),
            already_exists=False,
        )


async def offline_adk(runtime, event_id):
    intent = intent_for(event_id)
    runtime.parsed[event_id] = intent
    result = runtime.engine.process(event_id, intent)
    return {"agent_name": "shiftchain_agent", "final_state": result.state.value}


def recovery_workflow(repository: RecoveryRepository, scheduler: RecoveryScheduler, monkeypatch) -> CloudWorkflow:
    workflow = CloudWorkflow(config=cloud_config(), client=None, scheduler=scheduler)
    workflow.repository = lambda run_id: repository
    monkeypatch.setattr("shiftchain.cloud_workflow.GeminiIntentParser", lambda: type("P", (), {})())
    monkeypatch.setattr("shiftchain.cloud_workflow.run_event_through_adk", offline_adk)
    return workflow


def test_confirmation_after_early_wake_creates_g2_and_g2_verifies(monkeypatch) -> None:
    repository = RecoveryRepository()
    scheduler = RecoveryScheduler()
    workflow = recovery_workflow(repository, scheduler, monkeypatch)
    first_status, _ = workflow.resume(
        ResumePayload(run_id="RUN-DEMO-001", target_event_id="EVT-003", resume_generation=1),
        task_name="g1",
        task_attempt="0",
    )
    assert first_status == 204
    delivered = asyncio.run(workflow.deliver("RUN-DEMO-001", "EVT-004"))
    assert delivered["confirmation_schedule_result"] == "CONFIRMATION_RECORDED_RESUME_SCHEDULED"
    assert scheduler.created[-1][0].resume_generation == 2
    assert scheduler.created[-1][1] == 0
    status, result = workflow.resume(scheduler.created[-1][0], task_name="g2", task_attempt="0")
    assert status == 200 and result["result"]["state"] == RequestState.VERIFIED.value


def test_confirmation_before_g1_makes_g1_stale_and_g2_applies(monkeypatch) -> None:
    repository = RecoveryRepository()
    scheduler = RecoveryScheduler()
    workflow = recovery_workflow(repository, scheduler, monkeypatch)
    asyncio.run(workflow.deliver("RUN-DEMO-001", "EVT-004"))
    stale_status, stale = workflow.resume(
        ResumePayload(run_id="RUN-DEMO-001", target_event_id="EVT-003", resume_generation=1),
        task_name="g1",
        task_attempt="0",
    )
    assert stale_status == 204 and stale["result"] == "STALE_GENERATION_NO_OP"
    status, _ = workflow.resume(scheduler.created[-1][0], task_name="g2", task_attempt="0")
    assert status == 200
    assert repository.get_request("REQ-003").state == RequestState.VERIFIED


def test_duplicate_confirmation_and_multiple_g2_delivery_are_business_idempotent(monkeypatch) -> None:
    repository = RecoveryRepository()
    scheduler = RecoveryScheduler()
    workflow = recovery_workflow(repository, scheduler, monkeypatch)
    asyncio.run(workflow.deliver("RUN-DEMO-001", "EVT-004"))
    duplicate = asyncio.run(workflow.deliver("RUN-DEMO-001", "EVT-004"))
    assert duplicate["confirmation_schedule_result"] == "CONFIRMATION_ALREADY_RECORDED"
    assert len(scheduler.created) == 1
    g2 = scheduler.created[0][0]
    assert workflow.resume(g2, task_name="g2", task_attempt="0")[0] == 200
    assert workflow.resume(g2, task_name="g2", task_attempt="1")[0] == 204
    run = repository.get_run("RUN-DEMO-001")
    assert run.shifts["SHF-260827-M"].version == 1
    assert run.schedule_version == 1
    assert [entry.to_worker_id for entry in repository.custody_chain("SHF-260827-M")] == ["W-004", "W-005"]


class WebWorkflowStub:
    def __init__(self) -> None:
        self.resume_calls = 0

    def resume(self, payload, *, task_name, task_attempt):
        self.resume_calls += 1
        return 204, {}


def test_internal_route_rejects_anonymous_before_workflow() -> None:
    stub = WebWorkflowStub()
    web.get_workflow.cache_clear()
    web.get_oidc_validator.cache_clear()
    web.app.dependency_overrides[web.get_workflow] = lambda: stub
    # These functions are called directly, not through Depends, so replace caches for the request.
    original_workflow = web.get_workflow
    original_validator = web.get_oidc_validator
    web.get_workflow = lambda: stub
    web.get_oidc_validator = lambda: OIDCValidator("aud", "caller", verifier=lambda *_: {})
    try:
        response = TestClient(web.app).post(
            "/internal/tasks/resume",
            json={"run_id": "RUN-DEMO-001", "target_event_id": "EVT-003", "resume_generation": 1},
        )
        assert response.status_code == 401
        assert stub.resume_calls == 0
    finally:
        web.get_workflow = original_workflow
        web.get_oidc_validator = original_validator
        web.app.dependency_overrides.clear()


def test_canonical_health_is_documented_and_side_effect_free() -> None:
    client = TestClient(web.app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    paths = client.get("/openapi.json").json()["paths"]
    assert "/health" in paths
    assert "/healthz" not in paths
    assert "/healthz/" not in paths
