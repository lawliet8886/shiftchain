# Phase 2 Gate — RECOVERY PARTIAL

Date: 2026-08-25 (America/Sao_Paulo)

## Gate decision

The original latency blocker is resolved. The autonomous recovery flow passed in the real cloud. The overall gate is **PARTIAL** only because the exact `/healthz` path cannot return 200 through the Cloud Run Google Frontend; Phase 3 was not started.

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

## Recovery clarification and implementation

The earlier proposal to lengthen the delay was superseded by the approved resilience clarification:

> The 15-second task is an initial condition check, not a guarantee that external confirmation processing has completed. A verified confirmation advances the resume generation and enqueues a new authenticated Cloud Task without applying the transfer directly.

The implementation now uses task-first/commit-second for confirmation-triggered resume. EVT-004 validates through real Gemini and ADK, creates deterministic g2, then a Firestore transaction atomically persists confirmation evidence, g2 metadata and the new generation. A task-before-commit sees a future generation and returns retryable without mutation. g2 reloads Firestore, calls no Gemini, revalidates deterministically, applies once and performs independent readback.

## Successful recovery run

Run: `P2RECOVERY-20260825-001`

- EVT-003 delivered: `2026-08-25T13:39:37.694805Z`.
- EVT-003 completed WAITING: `2026-08-25T13:40:01.396068Z`.
- g1 dispatched: `2026-08-25T13:40:16.125687Z`.
- g1 persisted `WAIT_CONDITION_NOT_MET` at `2026-08-25T13:40:16.260073Z`; owner W-004 and both versions remained 0.
- EVT-004 delivered: `2026-08-25T13:40:41.674552Z`.
- EVT-004/Gemini completed in `15.099668s` at `2026-08-25T13:40:56.776736Z`.
- Confirmation and g2 persisted at `2026-08-25T13:40:56.669998Z`.
- g2 resume returned HTTP 200 in `0.847699s` without Gemini.
- `TRANSFER_APPLIED`: `2026-08-25T13:40:56.990219Z`.
- `TRANSFER_VERIFIED`: `2026-08-25T13:40:57.262426Z`.
- Final: REQ-003 VERIFIED, owner W-005, shift version 1, schedule version 1, custody W-004 → W-005.

No user action occurred after EVT-004 delivery; only Firestore reads observed completion.

## Recovery regression evidence

- Slice A rerun on revision `shiftchain-demo-00003-h8r`: VERIFIED through real Gemini/ADK; owner W-002; shift and schedule versions 1.
- Replayed stale g1: 204 and `STALE_GENERATION_NO_OP`.
- Replayed g2 after verification: 204 and `ALREADY_VERIFIED_NO_OP`.
- Future g3: retryable/non-2xx, no mutation; bounded test task removed afterward.
- Anonymous and wrong-audience requests: 401; wrong identity: 403; valid caller: 2xx.
- Final business versions remained exactly 1 and the queue was empty after testing.

## Health endpoint finding

Revision `shiftchain-demo-00003-h8r` serves 100% of traffic and registers `/healthz` in OpenAPI. Cloud Run rejects the exact path at the Google Frontend because its documented known issues reserve some paths ending in `z`.

- `/health`: HTTP 200.
- `/healthz/`: HTTP 200.
- `/healthz`: Google Frontend HTTP 404 before the container.

No second service, load balancer or other infrastructure was created to bypass the restriction. This is the sole remaining gate item.

## Freeze and security

- No deterministic-engine rules were weakened.
- No secret, OIDC token, Authorization header or service-account JSON key was stored or printed.
- No broad Editor/Owner role was granted to either ShiftChain service account.
- No forced 503, local sleep fallback, background worker, browser timer or Phase 3 feature was added.
- Freeze deviation: resilience clarification only; domain data, state machine and deterministic engine are unchanged.
