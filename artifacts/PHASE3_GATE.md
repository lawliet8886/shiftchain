# Phase 3 Gate — PASSED

Date: 2026-08-25 (America/Sao_Paulo)

## Gate decision

ShiftChain demonstrated an exactly-once business effect under real at-least-once Cloud Tasks delivery. The controlled lost-acknowledgement run committed and independently verified Noah → Emma, intentionally returned one HTTP 503, then accepted the native retry of the same task as `NO_OP_VERIFIED`. The retry made no second mutation. Phase 3 is **PASSED** and Phase 4 was not started.

## Failure scenario and safety

Run `P3RELIABILITY-FINAL-20260825` explicitly enabled `LOST_ACK_AFTER_VERIFY_ONCE` in `DEMO` mode. The setting and one-shot consumption are transactional Firestore fields, not process memory. The fault is disabled by default, rejected outside DEMO, scoped to REQ-003/EVT-003, and consumable only after REQ-003 is durable `VERIFIED` and `TRANSFER_VERIFIED` exists.

Judge Mode intentionally returns one HTTP 503 after the business transaction and independent verification have completed. This simulates a lost acknowledgement and proves that at-least-once task delivery does not duplicate the business effect.

## Real Cloud Tasks timeline

- Initial state: owner W-004 (Noah), shift v0, schedule v0, custody head `ledger:initial:SHF-260827-M`.
- EVT-003 reached `WAITING_CONFIRMATION`; g1 safely recorded `WAIT_CONDITION_NOT_MET`.
- EVT-004 persisted Emma's acceptance and scheduled g2.
- g2 task: `projects/gen-lang-client-0643751280/locations/us-central1/queues/shiftchain-resume/tasks/resume-4167da92a26ec96ffe4cbd97391e5668`.
- Generation: 2 on both application-visible deliveries.
- First delivery began `2026-08-25T14:31:18.285499Z`, created `TRANSFER_APPLIED` at `14:31:18.786562Z`, created `TRANSFER_VERIFIED` at `14:31:19.253198Z`, atomically consumed the fault at `14:31:19.527859Z`, and returned HTTP 503.
- No request, task creation, click or manual resume occurred after that 503.
- The same Cloud Task retried natively at `2026-08-25T14:31:35.304185Z`.
- The retry found REQ-003 already `VERIFIED`, performed the full persistent readback, wrote deterministic evidence `noop:EVT-003:g2` at `14:31:35.409364Z`, and returned HTTP 204.
- Cloud Run request logs show exactly two application-visible g2 requests: 503 then 204, both on revision `shiftchain-demo-00007-k8n` with user agent `Google-Cloud-Tasks`.
- Cloud Tasks headers recorded attempt/retry-count `0` for the injected 503 and `2` for the successful retry. No retry-count 1 request reached the application or Cloud Run request log; this platform telemetry does not participate in authentication or idempotency.
- Queue ended empty.

## Exactly-once proof

| Observation | Owner | Request | Shift version | Schedule version | Custody head | Result |
|---|---|---|---:|---:|---|---|
| Before first g2 | Noah (W-004) | WAITING_CONFIRMATION | 0 | 0 | initial assignment | ready to apply |
| After first g2 / HTTP 503 | Emma (W-005) | VERIFIED | 1 | 1 | `ledger:REQ-003:v1` | business succeeded, acknowledgement failed |
| Before retry readback | Emma (W-005) | VERIFIED | 1 | 1 | `ledger:REQ-003:v1` | existing effect found |
| After retry / HTTP 204 | Emma (W-005) | VERIFIED | 1 | 1 | `ledger:REQ-003:v1` | NO_OP_VERIFIED |

Custody remained exactly Noah → Emma. There is one `TRANSFER_APPLIED`, one `TRANSFER_VERIFIED`, one deterministic non-custody `NO_OP_VERIFIED`, one transfer custody edge, and no duplicate version increment. `TRANSFER_APPLIED` is the custody head; verification and no-op evidence never enter the custody chain.

The retry readback checked request state, intent, applied and verification records, shift owner/version, schedule version, custody head, predecessor owner, request and ledger idempotency keys, and uniqueness of both applied and verified records. Any inconsistency produces `INTEGRITY_ERROR`; it never reapplies.

## Normal-run regression

Run `P3RELIABILITY-B-20260825` left `fault_injection=null` and `failure_injection_used=false`. Its g2 task returned HTTP 200, created exactly one transfer and one verification, finished REQ-003 `VERIFIED`, owner W-005, shift v1 and schedule v1, and produced no `NO_OP_VERIFIED`. This proves the 503 is explicit test behavior, not the normal product path.

## Security and health regression

All security checks used real Cloud Tasks against final revision `shiftchain-demo-00007-k8n`:

- expected task-caller OIDC identity and audience: HTTP 204;
- no token: HTTP 401;
- valid task identity with wrong audience: HTTP 401;
- valid audience with wrong identity: HTTP 403.

Bounded non-2xx test tasks were deleted and the queue returned to zero. `GET /health` returned HTTP 200 with queue 0 → 0 and an unchanged Firestore reference update time. It invoked neither Gemini nor Firestore mutation nor task creation.

## Queue and cost guardrails

The existing queue configuration already provided a conservative real retry and was not changed: max attempts 5, min backoff 5s, max backoff 60s, max doublings 3, max retry duration 300s, max concurrency 2, and max dispatch rate 2/s.

The resource topology remains one named Firestore database (`shiftchain`), one Cloud Run service (`shiftchain-demo`), one Cloud Tasks queue (`shiftchain-resume`), the existing two service accounts, and the existing Gemini secret. Final Cloud Run scaling is min 0, max 2. No service, queue, database or observability stack was added.

## Verification

- Automated tests: 58 passed, 0 failed, coverage 55%.
- `compileall`: PASS.
- `pip check`: PASS; no broken requirements.
- `git diff --check`: PASS.
- Secret scan before commits: PASS; no credential-shaped content.
- Remote Git operations: none; repository has no configured remote.

## Final checklist

- [x] Phase 2 remains green
- [x] Failure injection is explicit opt-in, DEMO-only and disabled by default
- [x] Injection state and consumption persist in Firestore
- [x] Transactional one-shot behavior, including concurrency test
- [x] Injection occurs only after APPLIED, independent readback and VERIFIED
- [x] First g2 applied Noah → Emma exactly once
- [x] Business state remained VERIFIED after the designed HTTP 503
- [x] Same Cloud Task and generation retried natively
- [x] Retry invoked no Gemini and performed read-before-repeat
- [x] Retry produced deterministic `NO_OP_VERIFIED`
- [x] Shift and schedule versions remained 1 after retry
- [x] Custody remained Noah → Emma with no duplicate edge or changed head
- [x] One applied record and one verification record
- [x] Queue ended empty
- [x] Normal no-fault cloud run returned HTTP 200 and VERIFIED
- [x] Valid OIDC 2xx; anonymous 401; wrong audience 401; wrong identity 403
- [x] `/health` returned 200 without side effects
- [x] Tests, compileall, pip check and diff check passed
- [x] Secret scan passed and artifacts contain no secrets
- [x] Existing resources only; Cloud Run min 0, max 2
- [x] No Phase 4 activity

Freeze classification: **RELIABILITY IMPLEMENTATION ONLY**.
