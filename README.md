# ShiftChain

> Responsibility moves. ShiftChain keeps the truth.

ShiftChain turns messy operational handoff messages into safe, deterministic and auditable custody changes. Gemini 3.7 Flash is restricted to structured intent extraction. The domain engine owns validation, authorization, idempotency, concurrency checks, mutation and verification.

## Phase 3 status

The cloud vertical slice is deployed in the dedicated Google Cloud project `gen-lang-client-0643751280`. Firestore, Cloud Run, Cloud Tasks, Secret Manager and app-level OIDC validation are live. Phase 3 proves that a real Cloud Tasks retry after an intentionally lost acknowledgement preserves exactly one Noah → Emma business mutation. See `artifacts/PHASE3_GATE.md` and `artifacts/reliability_proof.json`.

## Reliability

Cloud Tasks is at-least-once infrastructure; ShiftChain does not claim or assume exactly-once delivery. Deterministic request and ledger idempotency keys protect mutations, while `APPLIED` and `VERIFIED` remain separate business states. Every retry reads persistent truth before considering another mutation.

When a request is already `VERIFIED`, ShiftChain validates the applied transfer, independent verification, versions, custody predecessor and head, owner, idempotency keys and record uniqueness. Valid evidence produces deterministic, non-custody `NO_OP_VERIFIED`; inconsistent evidence fails closed and is never reapplied.

The explicit DEMO-only `LOST_ACK_AFTER_VERIFY_ONCE` injection transactionally consumes one persisted fault only after commit and independent verification. Judge Mode then returns HTTP 503. The same real Cloud Task retries, discovers the verified effect, records `NO_OP_VERIFIED`, and returns 204 without changing owner, versions or custody.

## Phase 1 foundation

Implemented here: frozen HCO dataset, Pydantic intent schema, in-memory repository abstraction, deterministic reconciliation engine, append-only custody ledger, independent read-back verification, one ADK agent (`shiftchain_agent`), Gemini feasibility check, tests, and a local CLI demo.

The cloud adapter uses one named Firestore database, one Cloud Run service, one Cloud Tasks queue, a dedicated runtime identity, a dedicated task-caller identity and Secret Manager delivery. Phase 3 adds only the controlled reliability injection and evidence path. No remote GitHub, custom Dockerfile, CI/CD or additional cloud service is included.

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
