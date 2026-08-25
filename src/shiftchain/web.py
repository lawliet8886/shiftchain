from __future__ import annotations

from functools import lru_cache
import os

from fastapi import Body, FastAPI, Header, HTTPException, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict

from shiftchain.cloud_config import CloudConfig
from shiftchain.cloud_workflow import CloudWorkflow, FutureGenerationError
from shiftchain.oidc import OIDCAuthenticationError, OIDCAuthorizationError, OIDCValidator
from shiftchain.tasks import ResumePayload

app = FastAPI(title="ShiftChain", version="0.2.0")


class DeliverRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str


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
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>ShiftChain Phase 2</title>
<style>body{font:16px system-ui;max-width:960px;margin:32px auto;padding:0 16px;color:#17202a}button,input{padding:9px;margin:4px}pre{background:#f4f6f7;padding:16px;overflow:auto}.ok{color:#087830}</style>
</head><body><h1>ShiftChain</h1><p>Responsibility moves. ShiftChain keeps the truth.</p>
<p class="ok">Phase 2 cloud vertical slice — demo delay: 15 seconds.</p>
<button onclick="resetDemo()">New demo run</button><input id="run" placeholder="Run ID">
<button onclick="deliver('EVT-001')">Deliver EVT-001</button><button onclick="deliver('EVT-003')">Deliver EVT-003</button><button onclick="deliver('EVT-004')">Deliver EVT-004</button>
<pre id="out">Create or enter a run.</pre>
<script>
const out=document.getElementById('out'), run=document.getElementById('run');
async function resetDemo(){const r=await fetch('/api/demo/reset',{method:'POST'});const j=await r.json();run.value=j.run_id;await refresh()}
async function deliver(id){const r=await fetch('/api/events/'+id+'/deliver',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({run_id:run.value})});out.textContent=JSON.stringify(await r.json(),null,2);await refresh()}
async function refresh(){if(!run.value)return;const r=await fetch('/api/runs/'+run.value);out.textContent=JSON.stringify(await r.json(),null,2)}
setInterval(refresh,2000);
</script></body></html>"""


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    snapshot = get_workflow().snapshot(run_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="run not found")
    return JSONResponse(content=jsonable_encoder(snapshot))


@app.post("/api/demo/reset")
def reset_demo():
    return get_workflow().reset()


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
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if status_code == 204:
        return Response(status_code=204)
    return JSONResponse(status_code=status_code, content=jsonable_encoder(result))
