from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from shiftchain.agent import ShiftChainToolRuntime, run_event_through_adk
from shiftchain.frozen_data import candidate_context, frozen_repository, intent_for
from shiftchain.parser import GeminiIntentParser, MODEL_ID, detect_route, sanitized_error

CONTRACT_ID = "gemini-3.7-flash:structured-intent-1.0:prompt-2026-08-25"
ARTIFACT = Path(__file__).resolve().parents[2] / "artifacts" / "gemini_feasibility.json"


def _write_report(report: dict) -> None:
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def _passed_checkpoint() -> dict:
    try:
        prior = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if prior.get("contract_id") != CONTRACT_ID or prior.get("model") != MODEL_ID:
        return {}
    passed = {
        event_id: result
        for event_id, result in prior.get("fixtures", {}).items()
        if result.get("passed") is True
    }
    for result in passed.values():
        result.setdefault("model_id", MODEL_ID)
        result.setdefault("route", prior.get("route"))
        result.setdefault("attempt", 1)
        result.setdefault("result", "PASS")
        result.setdefault("error_type", None)
    return passed


def _comparison(actual, expected) -> dict:
    fields = (
        "intent_type",
        "from_worker_id",
        "to_worker_id",
        "shift_id",
        "target_request_id",
        "dependency_request_id",
        "confirmation",
        "confirmation_by_worker_id",
        "decision",
    )
    mismatches = {
        field: {"actual": getattr(actual, field), "expected": getattr(expected, field)}
        for field in fields
        if getattr(actual, field) != getattr(expected, field)
    }
    return {"passed": not mismatches, "mismatches": mismatches, "ambiguities": actual.ambiguities}


async def run_check() -> dict:
    route = detect_route()
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "model": MODEL_ID,
        "contract_id": CONTRACT_ID,
        "sdk": "google-genai",
        "sdk_version": version("google-genai"),
        "adk_version": version("google-adk"),
        "route": route.name if route else None,
        "credential_values_logged": False,
        "fixtures": _passed_checkpoint(),
        "adk": None,
        "status": "BLOCKED",
    }
    if route is None:
        probe_code = (
            "import json,time,google.auth; from google import genai; "
            "from shiftchain.parser import sanitized_error; started=time.perf_counter(); "
            "credentials,_=google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform']); "
            "result={'attempted':True,'route':'Gemini Developer API via existing ADC OAuth'}; "
            "\ntry:\n client=genai.Client(credentials=credentials); "
            f"client.models.generate_content(model='{MODEL_ID}',contents='Return exactly OK.'); result['success']=True"
            "\nexcept Exception as exc:\n result['success']=False; result['error']=sanitized_error(exc)"
            "\nresult['latency_ms']=round((time.perf_counter()-started)*1000); print(json.dumps(result))"
        )
        probe = subprocess.run(
            [sys.executable, "-c", probe_code],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        lines = [line for line in probe.stdout.splitlines() if line.strip()]
        report["access_probe"] = json.loads(lines[-1]) if lines else {
            "attempted": True,
            "route": "Gemini Developer API via existing ADC OAuth",
            "success": False,
            "error": "Probe process produced no structured result.",
        }
        report["error"] = (
            "No Gemini API key or configured Vertex AI project was found; the existing ADC OAuth "
            "probe was also unable to authenticate a model call."
        )
        return report
    try:
        parser = GeminiIntentParser(route=route)
        for event_id in ("EVT-001", "EVT-002", "EVT-003", "EVT-004", "AMB-001"):
            if report["fixtures"].get(event_id, {}).get("passed") is True:
                continue
            repository = frozen_repository()
            actual, telemetry = parser.parse(candidate_context(repository, event_id))
            report["fixtures"][event_id] = {
                **_comparison(actual, intent_for(event_id)),
                "model_id": telemetry.model,
                "route": telemetry.route,
                "attempt": telemetry.attempts,
                "result": "PASS" if _comparison(actual, intent_for(event_id))["passed"] else "FAIL",
                "latency_ms": telemetry.latency_ms,
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "error_type": None,
                "parsed": actual.model_dump(mode="json"),
            }
            _write_report(report)
        required = ("EVT-001", "EVT-002", "EVT-003", "EVT-004", "AMB-001")
        fixtures_passed = all(report["fixtures"].get(event_id, {}).get("passed") is True for event_id in required)
        if not fixtures_passed:
            report["status"] = "PARTIAL"
            return report

        evt2 = report["fixtures"]["EVT-002"]
        if not evt2.get("repeat_check", {}).get("passed"):
            repository = frozen_repository()
            repeated, telemetry = parser.parse(candidate_context(repository, "EVT-002"))
            repeated_comparison = _comparison(repeated, intent_for("EVT-002"))
            evt2["repeat_check"] = {
                **repeated_comparison,
                "model_id": telemetry.model,
                "route": telemetry.route,
                "attempt": telemetry.attempts,
                "result": "PASS" if repeated_comparison["passed"] else "FAIL",
                "latency_ms": telemetry.latency_ms,
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "error_type": None,
                "parsed": repeated.model_dump(mode="json"),
            }
            _write_report(report)
            if not repeated_comparison["passed"]:
                report["status"] = "PARTIAL"
                return report

        runtime = ShiftChainToolRuntime(frozen_repository(), parser)
        report["adk"] = await run_event_through_adk(runtime, "EVT-001")
        tools_passed = report["adk"]["tool_calls"] == [
            "read_event_context",
            "validate_intent",
            "apply_decision",
            "verify_outcome",
        ] and report["adk"]["final_state"] == "VERIFIED" and report["adk"]["current_owner_id"] == "W-002" and report["adk"]["shift_version"] == 1 and report["adk"]["schedule_version"] == 1
        report["status"] = "PASS" if fixtures_passed and tools_passed else "PARTIAL"
    except Exception as exc:  # evidence path must survive authentication/API failures
        report["status"] = "BLOCKED"
        report["error"] = sanitized_error(exc)
    return report


def main() -> None:
    report = asyncio.run(run_check())
    _write_report(report)
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
