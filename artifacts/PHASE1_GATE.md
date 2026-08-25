# Phase 1 gate evidence

- Evaluated: 2026-08-25, America/Sao_Paulo
- Overall status: PARTIAL
- Frozen tagline: “Responsibility moves. ShiftChain keeps the truth.”

## Offline deterministic core

- Python: 3.12.10
- Tests: 21 passed, 0 failed
- Coverage: 71% total
- Dependency integrity: `pip check` passed
- Compile check: passed
- CLI demo: passed
- EVT-001: VERIFIED, Maya → Liam
- EVT-002: VERIFIED, Liam → Sofia, dependent on REQ-001
- EVT-003: WAITING_CONFIRMATION, no ownership mutation
- EVT-004: confirmation rule VERIFIED; no async resume or transfer in Phase 1
- AMB-001: NEEDS_CLARIFICATION, no ownership mutation
- Custody chain for SHF-260826-E: W-001 → W-002 → W-003
- Final owner: W-003
- Final shift version: 2
- Final schedule version: 2

## Gemini and ADK live gate

- Intended model: `gemini-3.7-flash`
- SDK: `google-genai 2.19.0`
- ADK: `google-adk 2.7.1`
- One ADK agent: `shiftchain_agent`
- Agent shape check: passed, exactly four tools and zero subagents
- Live access: BLOCKED
- Environment evidence: no `GEMINI_API_KEY`, no `GOOGLE_API_KEY`, no configured Google Cloud project, and existing ADC has neither detected project nor quota project
- Real SDK authentication probe: attempted and rejected before inference with `No API key was provided`
- Live Gemini eval fixtures: not executed
- Live full EVT-001 ADK Runner flow: not executed
- Secret values logged: no

## Phase boundary

No Firestore, Cloud Tasks, Cloud Run, frontend, remote repository, Docker, IAM, monitoring, CI/CD or production deployment was created.

## Smallest unblock action

Provide either `GEMINI_API_KEY` for the Gemini Developer API, or set an authorized `GOOGLE_CLOUD_PROJECT`/`GOOGLE_CLOUD_LOCATION` route with ADC for Vertex AI, then run:

```powershell
.\.venv\Scripts\python -m shiftchain.gemini_check
```

The Phase 1 gate can pass only if all five fixture comparisons pass and the ADK Runner calls the four tools in order for EVT-001, ending in VERIFIED.

