from __future__ import annotations

from functools import lru_cache
from importlib.resources import files
import os

from fastapi import Body, FastAPI, Header, HTTPException, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict

from shiftchain.cloud_config import CloudConfig
from shiftchain.cloud_workflow import (
    CloudWorkflow,
    FutureGenerationError,
    IntegrityVerificationError,
    LostAcknowledgementAfterVerify,
)
from shiftchain.oidc import OIDCAuthenticationError, OIDCAuthorizationError, OIDCValidator
from shiftchain.tasks import ResumePayload

app = FastAPI(title="ShiftChain", version="0.2.0")


class DeliverRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str


class ResetDemoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reliability_proof: bool = True


@lru_cache(maxsize=1)
def get_config() -> CloudConfig:
    return CloudConfig.from_env()


@lru_cache(maxsize=1)
def get_workflow() -> CloudWorkflow:
    return CloudWorkflow.from_config(get_config())


@lru_cache(maxsize=1)
def get_oidc_validator() -> OIDCValidator:
    config = get_config()
    return OIDCValidator(audience=config.task_audience, expected_email=config.task_caller_email)


@app.get("/health", include_in_schema=True)
@app.get("/healthz/", include_in_schema=False)
@app.get("/healthz", include_in_schema=False)
def healthz() -> dict:
    """Process-only health check: no Gemini, Firestore or Tasks call.

    Cloud Run reserves some paths ending in ``z`` at the Google Frontend, so
    ``/health`` is the canonical endpoint. The old paths remain as unlisted
    local compatibility aliases only.
    """
    return {
        "status": "ok",
        "service": "shiftchain-demo",
        "model": os.environ.get("SHIFTCHAIN_MODEL", "gemini-3.7-flash"),
        "cloud_mode_configured": bool(os.environ.get("GOOGLE_CLOUD_PROJECT")),
    }


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return files("shiftchain").joinpath("judge_ui.html").read_text(encoding="utf-8")


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    snapshot = get_workflow().snapshot(run_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="run not found")
    return JSONResponse(content=jsonable_encoder(snapshot))


@app.post("/api/demo/reset")
def reset_demo(request: ResetDemoRequest = Body(default=ResetDemoRequest())):
    return get_workflow().reset(reliability_proof=request.reliability_proof)


@app.post("/api/events/{event_id}/deliver")
async def deliver_event(event_id: str, request: DeliverRequest):
    if event_id not in {"EVT-001", "EVT-002", "EVT-003", "EVT-004"}:
        raise HTTPException(status_code=404, detail="frozen event not found")
    try:
        result = await get_workflow().deliver(request.run_id, event_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return JSONResponse(content=jsonable_encoder(result))


@app.post("/internal/tasks/resume")
def resume_task(
    payload: ResumePayload = Body(...),
    authorization: str | None = Header(default=None),
    x_cloudtasks_taskname: str | None = Header(default=None),
    x_cloudtasks_taskretrycount: str | None = Header(default=None),
):
    try:
        get_oidc_validator().validate(authorization)
    except OIDCAuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except OIDCAuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        status_code, result = get_workflow().resume(
            payload,
            task_name=x_cloudtasks_taskname,
            task_attempt=x_cloudtasks_taskretrycount,
        )
    except FutureGenerationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LostAcknowledgementAfterVerify as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except IntegrityVerificationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if status_code == 204:
        return Response(status_code=204)
    return JSONResponse(status_code=status_code, content=jsonable_encoder(result))
