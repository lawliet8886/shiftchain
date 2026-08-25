# Phase 4 Gate — PASSED

Date: 2026-08-25 (America/Sao_Paulo)

## Gate decision

ShiftChain is now judge-facing without changing its frozen product design. A single English screen makes the responsibility journey the hero, exposes persistent and reliability evidence, and preserves manual causal delivery through EVT-004 followed by autonomous completion. Five of five real cloud rehearsals completed with both custody chains correct, one controlled HTTP 503, native retry, `NO_OP_VERIFIED`, unchanged versions, no duplicate custody and an empty queue. Phase 4 is **PASSED**; Phase 5 was not started.

## Product and 20-second test

At 1440 × 900, a first-time viewer sees the four-event stream, Maya → Liam → Sofia, Noah → Emma, system evidence, agent activity and compact current responsibilities without scrolling the page. Verified edges are solid, green and explicitly labeled; waiting is dashed, amber and labeled; failures and reliability outcomes use words as well as color. The composition reads as custody movement—not a calendar, chat surface or generic management dashboard.

The final state communicates in under 20 seconds: responsibility moved through Chain A; Chain B completed automatically after confirmation; the controlled retry verified an existing effect instead of repeating it. Browser measurements on the deployed page were 1440 px document width, 1440 px client width and 900 px document height at a 1440 × 900 viewport.

## Real cloud rehearsal evidence

All five runs used the deployed Cloud Run service, real Gemini 3.7 Flash, real ADK agent execution, named Firestore database, Cloud Tasks, OIDC and explicit `LOST_ACK_AFTER_VERIFY_ONCE`. No fixture replaced the backend.

| Run | Completed | Final custody | Retry outcome | Duplicate version/custody | Duration |
|---|---|---|---|---|---:|
| RUN-DEMO-002 | yes | Maya → Liam → Sofia; Noah → Emma | 503 → `NO_OP_VERIFIED` | no / no | 128.857 s |
| RUN-DEMO-003 | yes | Maya → Liam → Sofia; Noah → Emma | 503 → `NO_OP_VERIFIED` | no / no | 125.706 s |
| RUN-DEMO-004 | yes | Maya → Liam → Sofia; Noah → Emma | 503 → `NO_OP_VERIFIED` | no / no | 97.413 s |
| RUN-DEMO-005 | yes | Maya → Liam → Sofia; Noah → Emma | 503 → `NO_OP_VERIFIED` | no / no | 91.787 s |
| RUN-DEMO-006 | yes | Maya → Liam → Sofia; Noah → Emma | 503 → `NO_OP_VERIFIED` | no / no | 96.001 s |

Average: 107.953 seconds. Maximum: 128.857 seconds. Every run was below the 225-second rehearsal ceiling, used a new run ID, recorded g1 safe waiting, and made no POST/click after EVT-004. Detailed timestamps and stage latency are in `artifacts/demo_runs.json`.

## Presentation artifacts

- Final deployed screenshot: `docs/images/shiftchain-hero.png`.
- GitHub/video-ready architecture: `docs/architecture.svg`; editable source: `docs/architecture.mmd`.
- Public-quality judge README with setup and safe deployment.
- Internal judging alignment: `docs/JUDGING_MAP.md`.
- Continuous 3:35 English demo: `artifacts/demo_rehearsal.md`.
- Official-requirement readiness: `artifacts/submission_self_check.md`.
- Full current/history security scan: `artifacts/publication_audit.json`.

## Cloud, security and health regression

Final deployed revision `shiftchain-demo-00009-5cw` serves 100% of traffic with min instances 0 and max instances 2. No cloud resource or service was added. The existing Firestore database, queue, secret and service accounts remain active for final recording.

- `GET /health`: HTTP 200 with Gemini model and cloud mode correctly reported.
- expected Cloud Tasks OIDC identity and exact audience: HTTP 204;
- no token: HTTP 401;
- valid task identity with wrong audience: HTTP 401;
- valid audience with wrong identity: HTTP 403;
- bounded negative tasks deleted; final queue depth: 0;
- live page: four VERIFIED events, `NO_OP_VERIFIED`, no fresh console errors, no horizontal overflow;
- secrets remain in Secret Manager/local ignored environment only; no secret value was read, displayed or committed.

## Documentation and publication readiness

README, diagram, code, deployed services and demo tell the same architecture: Gemini extracts intent; ADK coordinates bounded tools; deterministic code controls mutation; Firestore holds durable truth; Cloud Tasks handles time and authenticated retry; Secret Manager supplies the model credential. A fresh temporary virtualenv successfully installed the repository and loaded the packaged FastAPI app and judge UI.

The current tree and all Git patch history contain no key-shaped values, private keys, OAuth tokens, JWTs, personal Windows paths, personal usernames, private emails, named real institutions or real personal data. The local `.env` is ignored by both Git and gcloud source upload and is untracked. Temporary Playwright snapshots and redundant local screenshots were removed. `PUBLICATION_SAFE = TRUE`. Repository remotes remain zero.

## Verification

- Automated tests: **59 passed, 0 failed**, coverage **55%**.
- `compileall`: PASS.
- `pip check`: PASS; no broken requirements.
- artifact JSON parse and architecture SVG parse: PASS.
- clean-environment package/UI spin-up: PASS.
- `git diff --check`: PASS.
- real Cloud rehearsal: 5/5 PASS.
- security and Git-history scan: PASS.
- remote Git operations: none.

## Final checklist

### Product

- [x] Responsibility Journey is the hero
- [x] Does not look like a calendar, chatbot or generic dashboard
- [x] Maya → Liam → Sofia is visually obvious
- [x] Noah → Emma waiting and verified states are visually obvious
- [x] Autonomous resume is visible in Agent Activity
- [x] 503, retry and `NO_OP_VERIFIED` are visible

### UI

- [x] One-screen, English-first judge UI at 1440 × 900
- [x] Functional Event Stream, Evidence, Agent Activity and compact responsibilities
- [x] Reset creates a new run without deleting history
- [x] Reliability proof explicitly ON
- [x] Zero clicks after EVT-004
- [x] Labels and state text do not depend on color alone

### Cloud and reliability

- [x] Real Gemini, ADK, Cloud Run, Firestore, Cloud Tasks and OIDC
- [x] Real, declared fault injection after VERIFIED
- [x] Native retry and `NO_OP_VERIFIED`
- [x] Versions and custody do not duplicate
- [x] `/health` 200 and queue clean
- [x] Existing resources preserved; no new service

### Demo and documentation

- [x] Definitive single-continuous-run script, normal speed
- [x] Planned duration 3:35 and real maximum 2:09
- [x] Visible `.run.app` Cloud proof
- [x] 5/5 successful real rehearsals with timings
- [x] README, architecture, reliability, security, limitations and provenance complete
- [x] Reproducible spin-up checked from a clean virtualenv
- [x] Official submission self-check prepared

### Publication and quality

- [x] Current-tree and Git-history secret scans
- [x] Private-data, local-path, username and institutional scans
- [x] `PUBLICATION_SAFE = TRUE`
- [x] Zero Git remotes; no publish/upload/submission
- [x] Tests, compile, pip, artifacts and diff green
- [x] No Phase 5 activity

Freeze classification: **PRESENTATION / PRODUCTION READINESS ONLY**.
