# ShiftChain judging map

Internal review map for the current All Things Agentic Hackathon criteria. This is preparation material, not a submission.

## Innovation & Operational Utility — 40%

| Judge question | ShiftChain proof |
|---|---|
| Does it remove real friction? | Human handoffs become verified responsibility mutations, not text suggestions. |
| Is the Taskmaster workflow autonomous? | EVT-003 waits; EVT-004 persists confirmation; Cloud Tasks resumes with zero further clicks. |
| Is there a meaningful twist? | A handoff of a handoff is validated against temporal custody before Liam can transfer Maya's responsibility to Sofia. |
| Does it take action? | Firestore owner, shift version, schedule version and custody head change transactionally. |
| Does it recover? | A controlled lost acknowledgement causes a real task retry and `NO_OP_VERIFIED`, without duplicate effect. |

## Architectural Discipline & Tech Stack — 30%

| Concern | Evidence |
|---|---|
| Bounded AI | Gemini 3.7 Flash emits schema-constrained intent from bounded candidates only. |
| Agent framework | One Google ADK agent with four scoped tools. |
| Deterministic authority | Consent, availability, dependency, custody and mutation are enforced in code. |
| Persistent state | Named Firestore database stores runs, checkpoints, ledger and verification evidence. |
| Temporal execution | Cloud Tasks provides g1/g2 wakeups; generation checks handle early, stale and future delivery. |
| Security | Exact OIDC audience and identity, least-privilege service accounts, Secret Manager reference. |
| Reliability | APPLIED differs from VERIFIED; retries read before repeating under at-least-once delivery. |

## Demo & Production Readiness — 30%

| Requirement | Planned judge proof |
|---|---|
| Live execution | One continuous real-cloud run in the judge UI. |
| Google Cloud proof | The visible `.run.app` address plus `Live on Google Cloud` and architecture evidence. |
| Clear demo | Responsibility Journey is the hero; event stream, evidence and activity explain causal progress. |
| Architecture | `docs/architecture.svg` plus editable `docs/architecture.mmd`. |
| Reproducibility | README includes local setup, tests and safe Google Cloud deployment outline. |
| Stability | Five fresh runs must complete both chains and reliability proof without duplication. |

## Submission baseline

- Category: Taskmaster.
- Gemini 3.7 Flash satisfies the Gemini 3.5-or-newer requirement.
- Google ADK is the required Google agent framework.
- Cloud Run, Firestore, Cloud Tasks and Secret Manager provide the Google Cloud backend.
- English UI and documentation are ready; the final video must remain under four minutes and be public on YouTube or Vimeo when later authorized.
