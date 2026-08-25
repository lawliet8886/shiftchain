# ShiftChain

> Responsibility moves. ShiftChain keeps the truth.

ShiftChain Phase 1 is a local proof that messy operational handoff messages can become safe, deterministic and auditable custody changes. Gemini 3.7 Flash is restricted to structured intent extraction. The domain engine owns validation, authorization, idempotency, concurrency checks, mutation and verification.

## Phase 1 boundary

Implemented here: frozen HCO dataset, Pydantic intent schema, in-memory repository abstraction, deterministic reconciliation engine, append-only custody ledger, independent read-back verification, one ADK agent (`shiftchain_agent`), Gemini feasibility check, tests, and a local CLI demo.

Explicitly absent: Firestore, Cloud Tasks, Cloud Run, final UI, remote GitHub, Docker, CI/CD, IAM, monitoring and production deployment.

## Run locally

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m shiftchain.demo
.\.venv\Scripts\python -m shiftchain.gemini_check
```

The demo uses the frozen structured fixtures so its state transitions are reproducible offline. `gemini_check` performs a real structured-output call when either a Gemini API key or a Vertex AI/ADC route is available. It reports route, model, SDK, latency and a sanitized error; it never prints credentials.

## Safety invariant

The model proposes a schema-valid intent only. Candidate IDs are bounded before the domain engine sees them. Every transfer is revalidated against current ownership, availability, conflicts, dependency head, consent, authorization, run validity, schedule version and shift version. A successful commit becomes `APPLIED`; a separate repository read-back is required for `VERIFIED`.

