# Phase 1 gate evidence

- Evaluated: 2026-08-25, America/Sao_Paulo
- Overall status: PASS
- Frozen tagline: “Responsibility moves. ShiftChain keeps the truth.”

## Offline deterministic core

- Python: 3.12.10
- Tests: 21 passed, 0 failed
- Coverage: 65% total; deterministic engine 75%, models 98%, repository 92%
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

## Paid access recovery

- The initial Free Tier attempt was blocked by the 20-request quota and intermittent 503 capacity errors.
- The user confirmed that paid billing was activated on the project associated with the configured API key.
- The SDK does not expose a billing-tier flag, so the observable proof is a successful authenticated, usage-bearing, structured-output inference after activation.
- Credentials remained only in the ignored `.env`; no credential value was printed or persisted in evidence.

## Gemini live evals

- Model: `gemini-3.7-flash`
- Route: Gemini Developer API
- SDK: `google-genai 2.19.0`
- Structured output: Pydantic/JSON Schema validation passed
- Candidate bounding: passed; no returned identifier fell outside the supplied candidates
- EVT-001: PASS — W-001 → W-002, SHF-260826-E, confirmation PRESENT
- EVT-002: PASS twice — W-002 → W-003, SHF-260826-E, dependency REQ-001, confirmation PRESENT
- EVT-003: PASS — W-004 → W-005, SHF-260827-M, confirmation ABSENT
- EVT-004: PASS — CONFIRM_REQUEST, REQ-003, confirmer W-005, ACCEPT
- AMB-001: PASS — UNKNOWN with explicit ambiguities; deterministic outcome NEEDS_CLARIFICATION and no mutation

Per-fixture timestamps, attempts, latency, parsed fields and non-sensitive diagnostics are stored in `artifacts/gemini_feasibility.json`.

## ADK Runner live gate

- One agent: `shiftchain_agent`
- Subagents: zero
- Real tool order: `read_event_context` → `validate_intent` → `apply_decision` → `verify_outcome`
- Input: natural-language EVT-001; no manually injected structured fixture
- Parsed transfer: W-001 → W-002, SHF-260826-E, confirmation by W-002
- Final state: VERIFIED
- Current owner: W-002
- Shift version: 1
- Schedule version: 1
- Ledger: `ledger:initial:SHF-260826-E` → `ledger:REQ-001:v1`
- Independent readback checks: owner, custody head, shift version, schedule version, request and predecessor all matched

## Security and repository gate

- High-confidence secret matches in tracked/versionable files: 0
- High-confidence secret matches in Git history: 0
- High-confidence secret matches in artifacts: 0
- `.env` ignored: yes
- `.env` tracked: no
- Remote repositories: 0
- Working branch: `main`

## Phase boundary

No Firestore, Cloud Tasks, Cloud Run, IAM, service account, frontend, Judge Mode, OIDC, deployment, remote GitHub, video or Devpost work was created or started.

## Definitive T+6h gate

- [x] Project clean and isolated
- [x] Provenance intact
- [x] Deterministic engine passing
- [x] Maya → Liam → Sofia passing locally
- [x] EVT-003 reaches WAITING_CONFIRMATION
- [x] Idempotency and compare-and-swap passing
- [x] Historical custody reconstruction passing
- [x] Ambiguity fails closed
- [x] Real `gemini-3.7-flash` access
- [x] Five live fixtures passing
- [x] EVT-002 repeated live semantic check passing
- [x] Structured output and candidate bounding passing
- [x] Real ADK Runner EVT-001 reaches VERIFIED
- [x] Tests, compile, dependency and demo checks passing
- [x] Secret scan clean
- [x] No Phase 2 activity

