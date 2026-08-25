# Phase 2 Gate — BLOCKED

Date: 2026-08-25 (America/Sao_Paulo)

## Gate decision

Phase 2 is **not passed**. Phase 3 was not started.

## Confirmed cloud environment

- Project: `gen-lang-client-0643751280` (`concurso`), ACTIVE, billing enabled.
- Firestore: named Native database `shiftchain`, `us-central1`, deletion protection enabled.
- Cloud Run: `shiftchain-demo`, runtime identity `shiftchain-runtime`, min 0, max 2.
- Cloud Tasks: queue `shiftchain-resume`, `us-central1`, 15-second demo schedule.
- Task identity: `shiftchain-task-caller` with app-level OIDC validation.
- Secret: `shiftchain-gemini-api-key`, delivered to Cloud Run by Secret Manager reference.

## Passing evidence

- Local compile and 34 tests passed, including OIDC, task generation, checkpoint rehydration and resume-without-Gemini tests.
- Real OIDC smoke task reached `/internal/tasks/resume` and returned HTTP 204.
- Anonymous and wrong-audience tasks returned HTTP 401; valid token from the wrong identity returned HTTP 403.
- Slice A `P2TEST-SLICE-A-20260825`: EVT-001 completed through Cloud Run → Gemini 3.7 Flash → ADK → deterministic engine → Firestore transaction → readback. Final state `VERIFIED`, owner `W-002`, shift version 1, schedule version 1.
- Minimal UI, run snapshot endpoint and anonymous internal-route rejection were reached through the official Cloud Run proxy.

## Blocking evidence

Classification: **CLOUD TASKS BLOCKER caused by external Gemini latency under the frozen 15-second scenario**.

- Action: deliver EVT-003, wait for `WAITING_CONFIRMATION` and a real task scheduled at +15 seconds, then deliver EVT-004 immediately.
- Attempt B1 deliberately included a Firestore observation before EVT-004 and missed the window; preserved as timing evidence.
- Attempt B2 dispatched EVT-004 0.95 seconds after EVT-003 completed. The EVT-004 Cloud Run request took 27.720509 seconds. The wake arrived first and safely returned 204 with no mutation.
- Attempt B3 dispatched EVT-004 0.41 seconds after EVT-003 completed. EVT-004 still took 16.051062 seconds; the wake completed first and safely no-op'd.
- Final state in B2/B3: REQ-003 `WAITING_CONFIRMATION`, confirmation evidence present, owner `W-004`, shift version 0, schedule version 0, no transfer ledger, no verification record.

Probable cause: current real Gemini Developer API latency for EVT-004 is greater than the frozen 15-second demonstration window. The application is fail-closed and behaved correctly.

Proposed resolution for a future authorized recovery: either lengthen the demo delay enough to cover observed p95 model latency or explicitly approve a product-level timing/retry design. Neither was done because this phase freezes `DEMO_DELAY_SECONDS=15` and forbids silent fallbacks/failure injection.

## Freeze and security

- No deterministic-engine rules were weakened.
- No secret, OIDC token, Authorization header or service-account JSON key was stored or printed.
- No broad Editor/Owner role was granted to either ShiftChain service account.
- No forced 503, local sleep fallback, background worker, browser timer or Phase 3 feature was added.
