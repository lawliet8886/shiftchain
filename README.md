# ShiftChain

> Responsibility moves. ShiftChain keeps the truth.

ShiftChain turns messy operational handoff messages into safe, deterministic and auditable custody changes. Gemini 3.7 Flash is restricted to structured intent extraction. The domain engine owns validation, authorization, idempotency, concurrency checks, mutation and verification.

## Phase 2 status

The cloud vertical slice is deployed in the dedicated Google Cloud project `gen-lang-client-0643751280`. Firestore, Cloud Run, Cloud Tasks, Secret Manager and app-level OIDC validation are live. The autonomous resume is latency-independent: an early g1 wake safely records an unmet condition, and a later verified confirmation advances the generation and creates an immediate authenticated g2 wake. The recovery run finished Noah → Emma exactly once. Phase 2 passed after approving `/health` as the canonical Cloud Run-safe health endpoint; the original `/healthz` 404 remains preserved in the gate evidence. See `artifacts/PHASE2_GATE.md`. Phase 3 has not started.

## Phase 1 foundation

Implemented here: frozen HCO dataset, Pydantic intent schema, in-memory repository abstraction, deterministic reconciliation engine, append-only custody ledger, independent read-back verification, one ADK agent (`shiftchain_agent`), Gemini feasibility check, tests, and a local CLI demo.

The Phase 2 adapter adds a named Firestore database, one Cloud Run service, one Cloud Tasks queue, a dedicated runtime identity, a dedicated task-caller identity and Secret Manager delivery. No remote GitHub, custom Dockerfile, CI/CD, failure injection or Phase 3 work is included.

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
