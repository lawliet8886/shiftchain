from __future__ import annotations

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
from shiftchain.tasks import CloudTaskScheduler, ResumePayload, task_id_for
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
    def __init__(self) -> None:
        self.inner = frozen_repository()
        ReconciliationEngine(self.inner).process("EVT-003", intent_for("EVT-003"))
        self.metadata = {
            "request_id": "REQ-003",
            "workflow_status": RequestState.WAITING_CONFIRMATION.value,
            "resume_generation": 1,
            "confirmation_evidence": {"confirmed_by_worker_id": "W-005"},
            "idempotency_key": "request:RUN-DEMO-001:REQ-003",
        }

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def event_metadata(self, event_id: str):
        assert event_id == "EVT-003"
        request = self.inner.get_request("REQ-003")
        self.metadata["workflow_status"] = request.state.value
        return self.metadata


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
