from __future__ import annotations

import os
from dataclasses import dataclass, field

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from shiftchain.engine import ReconciliationEngine
from shiftchain.frozen_data import candidate_context
from shiftchain.models import RequestRecord, StructuredIntent
from shiftchain.parser import GeminiIntentParser, GeminiRoute, MODEL_ID
from shiftchain.repository import ShiftChainRepository

AGENT_NAME = "shiftchain_agent"
APP_NAME = "shiftchain_phase1"


@dataclass
class ShiftChainToolRuntime:
    repository: ShiftChainRepository
    parser: GeminiIntentParser
    engine: ReconciliationEngine = field(init=False)
    parsed: dict[str, StructuredIntent] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.engine = ReconciliationEngine(self.repository)

    def read_event_context(self, event_id: str) -> dict:
        """Read one event and its bounded worker, shift and request candidates."""
        return candidate_context(self.repository, event_id).prompt_payload()

    def validate_intent(self, event_id: str) -> dict:
        """Parse with the structured Gemini route, then preview deterministic validation without mutation."""
        context = candidate_context(self.repository, event_id)
        intent, telemetry = self.parser.parse(context)
        event = context.source_event
        request = RequestRecord(request_id=event.request_id, source_event_id=event.event_id, run_id=event.run_id, intent=intent)
        decision = self.engine.validate(event.run_id, request, intent)
        self.parsed[event_id] = intent
        return {
            "intent": intent.model_dump(mode="json"),
            "deterministic_state": decision.state.value,
            "reason_codes": list(decision.reason_codes),
            "model": telemetry.model,
            "sdk": telemetry.sdk,
            "route": telemetry.route,
            "latency_ms": telemetry.latency_ms,
        }

    def apply_decision(self, event_id: str) -> dict:
        """Apply only a previously parsed intent through the deterministic engine."""
        intent = self.parsed.get(event_id)
        if intent is None:
            return {"state": "FAILED", "reason_codes": ["VALIDATE_INTENT_MUST_RUN_FIRST"]}
        result = self.engine.process(event_id, intent)
        return result.model_dump(mode="json")

    def verify_outcome(self, event_id: str) -> dict:
        """Read back request, verification record and custody chain; never infer success from tool history."""
        event = self.repository.get_event(event_id)
        if event is None:
            return {"state": "FAILED", "reason_codes": ["EVENT_NOT_FOUND"]}
        request = self.repository.get_request(event.request_id)
        if request is None:
            return {"state": "FAILED", "reason_codes": ["REQUEST_NOT_FOUND"]}
        verification = self.repository.get_verification(request.request_id)
        chain = ()
        if request.intent and request.intent.shift_id:
            chain = self.repository.custody_chain(request.intent.shift_id)
        return {
            "state": request.state.value,
            "verification": verification.model_dump(mode="json") if verification else None,
            "custody": [entry.to_worker_id for entry in chain],
        }


def configure_adk_route(route: GeminiRoute) -> None:
    if route.name.startswith("Vertex AI"):
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
        if route.project:
            os.environ["GOOGLE_CLOUD_PROJECT"] = route.project
        os.environ["GOOGLE_CLOUD_LOCATION"] = route.location or "global"
    else:
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "FALSE"
        os.environ["GOOGLE_GENAI_USE_ENTERPRISE"] = "FALSE"


def build_agent(runtime: ShiftChainToolRuntime) -> LlmAgent:
    return LlmAgent(
        name=AGENT_NAME,
        model=MODEL_ID,
        description="Coordinates one safe ShiftChain handoff without owning business decisions.",
        instruction=(
            "You coordinate one ShiftChain event. For the event_id in the user message, call exactly "
            "read_event_context, validate_intent, apply_decision, and verify_outcome in that order. "
            "Never invent IDs, bypass a tool, or reinterpret a deterministic rejection. After the tools, "
            "return a concise JSON-like summary with the final state."
        ),
        tools=[
            runtime.read_event_context,
            runtime.validate_intent,
            runtime.apply_decision,
            runtime.verify_outcome,
        ],
    )


async def run_event_through_adk(runtime: ShiftChainToolRuntime, event_id: str) -> dict:
    configure_adk_route(runtime.parser.route)
    agent = build_agent(runtime)
    session_service = InMemorySessionService()
    session_id = f"session-{event_id.lower()}"
    user_id = "phase1-evaluator"
    await session_service.create_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
    runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)
    tool_calls: list[str] = []
    final_text = ""
    message = types.Content(role="user", parts=[types.Part.from_text(text=f"Process event_id {event_id}.")])
    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=message):
        if event.content:
            for part in event.content.parts or []:
                if part.function_call:
                    tool_calls.append(part.function_call.name or "")
                if part.text and event.is_final_response():
                    final_text = part.text
    stored_event = runtime.repository.get_event(event_id)
    stored_request = runtime.repository.get_request(stored_event.request_id) if stored_event else None
    run = runtime.repository.get_run(stored_event.run_id) if stored_event else None
    shift_id = stored_request.intent.shift_id if stored_request and stored_request.intent else None
    shift = run.shifts.get(shift_id) if run and shift_id else None
    custody = runtime.repository.custody_chain(shift_id) if shift_id else ()
    return {
        "agent_name": agent.name,
        "tool_calls": tool_calls,
        "final_state": stored_request.state.value if stored_request else None,
        "final_text": final_text,
        "current_owner_id": shift.current_owner_id if shift else None,
        "shift_version": shift.version if shift else None,
        "schedule_version": run.schedule_version if run else None,
        "ledger_ids": [entry.ledger_id for entry in custody],
        "parsed_intent": runtime.parsed[event_id].model_dump(mode="json") if event_id in runtime.parsed else None,
    }
