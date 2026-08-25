from __future__ import annotations

import json
import os
import re
import subprocess
import time
import warnings
from dataclasses import dataclass
from importlib.metadata import version

from google import genai
import google.auth
from google.genai import types

from shiftchain.models import CandidateContext, StructuredIntent

MODEL_ID = "gemini-3.7-flash"


class CandidateBoundaryError(ValueError):
    pass


@dataclass(frozen=True)
class GeminiRoute:
    name: str
    project: str | None = None
    location: str | None = None


@dataclass(frozen=True)
class ParseTelemetry:
    model: str
    sdk: str
    sdk_version: str
    route: str
    latency_ms: int


def detect_route() -> GeminiRoute | None:
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        return GeminiRoute(name="Gemini Developer API")
    project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCLOUD_PROJECT")
    if not project:
        try:
            result = subprocess.run(
                ["gcloud", "config", "get-value", "project"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            candidate = result.stdout.strip()
            if result.returncode == 0 and candidate and candidate != "(unset)":
                project = candidate
        except (OSError, subprocess.SubprocessError):
            project = None
    if not project:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                credentials, detected_project = google.auth.default()
            project = detected_project or getattr(credentials, "quota_project_id", None)
        except Exception:
            project = None
    if project:
        return GeminiRoute(
            name="Vertex AI via Application Default Credentials",
            project=project,
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "global"),
        )
    return None


def client_for(route: GeminiRoute) -> genai.Client:
    if route.name == "Gemini Developer API":
        return genai.Client()
    return genai.Client(vertexai=True, project=route.project, location=route.location)


class GeminiIntentParser:
    def __init__(self, route: GeminiRoute | None = None, model: str = MODEL_ID) -> None:
        self.route = route or detect_route()
        if self.route is None:
            raise RuntimeError("No Gemini API key or Vertex AI project route is configured")
        self.model = model
        self.client = client_for(self.route)

    def parse(self, context: CandidateContext) -> tuple[StructuredIntent, ParseTelemetry]:
        instruction = (
            "Extract operational intent only. Use only candidate IDs supplied in the input. "
            "Do not decide whether a transfer is valid and do not invent missing facts. "
            "For ambiguous people, shifts, senders, dates, consent, or references, set intent_type "
            "to UNKNOWN or populate ambiguities. Evidence must quote only the source message. "
            "A recipient explicitly not confirmed means confirmation ABSENT."
        )
        started = time.perf_counter()
        response = self.client.models.generate_content(
            model=self.model,
            contents=json.dumps(context.prompt_payload(), ensure_ascii=False),
            config=types.GenerateContentConfig(
                system_instruction=instruction,
                response_mime_type="application/json",
                response_schema=StructuredIntent,
                temperature=0,
                seed=17,
                thinking_config=types.ThinkingConfig(thinking_level="low"),
            ),
        )
        latency_ms = round((time.perf_counter() - started) * 1000)
        parsed = response.parsed
        intent = parsed if isinstance(parsed, StructuredIntent) else StructuredIntent.model_validate_json(response.text)
        self.enforce_candidate_boundary(intent, context)
        telemetry = ParseTelemetry(
            model=self.model,
            sdk="google-genai",
            sdk_version=version("google-genai"),
            route=self.route.name,
            latency_ms=latency_ms,
        )
        return intent, telemetry

    @staticmethod
    def enforce_candidate_boundary(intent: StructuredIntent, context: CandidateContext) -> None:
        worker_ids = (intent.from_worker_id, intent.to_worker_id, intent.confirmation_by_worker_id)
        for worker_id in filter(None, worker_ids):
            if worker_id not in context.worker_candidates:
                raise CandidateBoundaryError(f"worker ID outside candidate set: {worker_id}")
        if intent.shift_id and intent.shift_id not in context.shift_candidates:
            raise CandidateBoundaryError(f"shift ID outside candidate set: {intent.shift_id}")
        request_ids = (intent.target_request_id, intent.dependency_request_id)
        for request_id in filter(None, request_ids):
            if request_id not in context.request_candidates:
                raise CandidateBoundaryError(f"request ID outside candidate set: {request_id}")


def sanitized_error(exc: Exception) -> str:
    text = f"{type(exc).__name__}: {exc}"
    text = re.sub(r"AIza[0-9A-Za-z_-]{20,}", "[REDACTED_API_KEY]", text)
    text = re.sub(r"(?i)bearer\s+[A-Za-z0-9._~+/-]+=*", "Bearer [REDACTED]", text)
    text = re.sub(r"(?i)(api[_-]?key[=: ]+)[^\s,;]+", r"\1[REDACTED]", text)
    return text[:600]
