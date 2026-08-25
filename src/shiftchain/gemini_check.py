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
        "sdk": "google-genai",
        "sdk_version": version("google-genai"),
        "adk_version": version("google-adk"),
        "route": route.name if route else None,
        "credential_values_logged": False,
        "fixtures": {},
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
            repository = frozen_repository()
            actual, telemetry = parser.parse(candidate_context(repository, event_id))
            report["fixtures"][event_id] = {
                **_comparison(actual, intent_for(event_id)),
                "latency_ms": telemetry.latency_ms,
                "parsed": actual.model_dump(mode="json"),
            }
        runtime = ShiftChainToolRuntime(frozen_repository(), parser)
        report["adk"] = await run_event_through_adk(runtime, "EVT-001")
        fixtures_passed = all(item["passed"] for item in report["fixtures"].values())
        tools_passed = report["adk"]["tool_calls"] == [
            "read_event_context",
            "validate_intent",
            "apply_decision",
            "verify_outcome",
        ] and report["adk"]["final_state"] == "VERIFIED"
        report["status"] = "PASS" if fixtures_passed and tools_passed else "PARTIAL"
    except Exception as exc:  # evidence path must survive authentication/API failures
        report["status"] = "BLOCKED"
        report["error"] = sanitized_error(exc)
    return report


def main() -> None:
    report = asyncio.run(run_check())
    artifact = Path(__file__).resolve().parents[2] / "artifacts" / "gemini_feasibility.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
