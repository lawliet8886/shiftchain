# Submission readiness self-check

Checked against the current All Things Agentic official rules, FAQ, updates, submission requirements and judging criteria on 2026-08-25. This file records readiness only: Phase 4 did **not** publish a repository, upload a final video, or submit to Devpost.

| Requirement | Status | Evidence |
|---|---|---|
| New contest-period project | READY | `PROJECT_PROVENANCE.md` records local creation and phase history. |
| Eligible Gemini model | READY | Real `gemini-3.7-flash` calls are used for bounded intent extraction. |
| Google agent framework | READY | A real Google ADK Runner executes the single `shiftchain_agent`. |
| Google Cloud backend | READY | Cloud Run, Firestore, Cloud Tasks, Secret Manager and OIDC are live in `us-central1`. |
| English support | READY | UI, README, architecture and demo script are English-first. |
| Judge-facing README | READY | Friction, agent rationale, demo story, stack, security, setup, deployment, tests, limitations and compliance are concise and public-ready. |
| Reproducible spin-up | READY | README local install, environment, tests and launch instructions were checked against package entry points. |
| Architecture diagram | READY | `docs/architecture.svg` plus editable `docs/architecture.mmd`. |
| Demo below four minutes | READY | Planned 3:35; five measured cloud runs were 1:32–2:09. Final recording is intentionally deferred. |
| Visible Google Cloud proof | READY | Deployed `.run.app` URL remains visible; UI badges identify Google Cloud, Gemini and ADK. |
| Repository requirement | PREPARED, NOT PUBLISHED | Repository is locally audited and has zero remotes. Publication/sharing is a later explicit phase. |
| Public YouTube/Vimeo video | PREPARED, NOT UPLOADED | Continuous 3:35 English script exists; recording/upload is prohibited in Phase 4. |
| Synthetic data | READY | Harborlight Community Operations, workers, shifts and messages are fictional. |
| Provenance | READY | Project and code provenance are documented. |
| Third-party rights | READY | No third-party application code, brand asset, personal image, audio or dataset is included. |
| Limitations disclosed | READY | README identifies frozen events, synthetic organization, one-week context and absent HR/payroll/integration scope. |

## Judging alignment

- **Innovation & Operational Utility (40%)**: chained handoffs, dependency-aware custody, durable waiting, autonomous resume and real mutation.
- **Architectural Discipline (30%)**: bounded Gemini intent, deterministic mutation, persistent Firestore state, authenticated Cloud Tasks, version preconditions and read-before-repeat.
- **Demo & Production Readiness (30%)**: live Cloud deployment, one-screen story, architecture, reproducible setup, five rehearsals and visible reliability proof.

## Publication boundary

The final repository URL, video URL, English captions if needed, Devpost fields and collaborator sharing must be completed only after explicit authorization. No bonus integration, social post, submission, upload or Phase 5 work occurred here.
