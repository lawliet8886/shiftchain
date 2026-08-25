# Five-minute judge simulation and red team

Inputs used: planned public GitHub landing page, README, hero and reliability screenshots, architecture SVG, hosted application, final narration and Devpost draft. The source code was not executed for scoring.

## Ten-question simulation

| Question | Finding |
|---|---|
| Friction understood in 20 seconds? | Yes. The first paragraph and Maya → Liam → Sofia make chained custody concrete. |
| Why an agent? | Yes. Waiting, waking and finishing later distinguish it from a text response. |
| Real action visible? | Yes. Owners, schedule versions, custody records and VERIFIED state change. |
| Temporal autonomy visible? | Yes. EVT-004 is the final click; generation two resumes through Cloud Tasks. |
| Google Cloud obvious? | Yes. `.run.app`, UI badges, README and diagram all name the actual services. |
| Gemini versus deterministic authority clear? | Yes. The separation is repeated consistently without claiming Gemini mutates truth. |
| Architecture understandable? | Yes. One diagram maps browser, Cloud Run, ADK/Gemini, deterministic engine, Firestore, Cloud Tasks/OIDC and Secret Manager. |
| Reliability proven? | Yes. The UI explicitly shows intentional HTTP 503, retry, unchanged versions and `NO_OP_VERIFIED`. |
| Reproducible? | Yes. Setup/deploy commands and clean-clone test cover the judge path; a Gemini key remains correctly external. |
| Memorable later? | Likely. “Responsibility moves. ShiftChain keeps the truth.” plus read-before-repeat creates a distinct story. |

## Scores

| Official criterion | Score | Critical rationale |
|---|---:|---|
| Innovation & Operational Utility | **4.3 / 5** | Strong specific friction, chained custody and autonomous delayed completion. The frozen synthetic scenario limits breadth and production-domain evidence. |
| Architectural Discipline & Tech Stack | **4.7 / 5** | Excellent separation of interpretation and authority, durable generations, OIDC, independent verification and retry safety. It remains a focused MVP rather than a broad production platform. |
| Demo & Production Readiness | **4.5 / 5** | Clear one-screen proof, hosted app, diagram, reproducible setup and five rehearsals. Final score still depends on the human recording quality and final Devpost assembly. |

Weighted internal estimate: **4.47 / 5** before the final video exists. This is an internal readiness estimate, not a prize prediction.

## Red-team findings

1. **“This is schedule software.”** Counterevidence: custody is the visual hero; the schedule list is deliberately compact context. Avoid lingering on the four responsibility rows in the video.
2. **“Gemini is decorative.”** The bounded extraction is real, but deterministic fixtures could create that impression. Narration must show the human-language message and explicitly state why probabilistic interpretation is separated from authority.
3. **“This is a normal workflow, not an agent.”** Emphasize durable waiting, asynchronous generations, autonomous wake, revalidation, mutation and verification—not the four buttons.
4. **“The 503 is fake.”** It is controlled, not accidental. The strongest proof is that it fires only after verified business success and a native Cloud Tasks delivery returns. Say this before showing it.
5. **“Exactly-once is exaggerated.”** Public copy correctly claims an exactly-once *business effect* under at-least-once delivery, not exactly-once infrastructure.
6. **“The demo could be staged.”** The visible `.run.app` URL, live timing, zero-click boundary and changing persistent evidence reduce this risk. The final recording must remain continuous at 1×.
7. **“Synthetic data means no utility.”** Synthetic data is a privacy/compliance choice. Keep future-domain claims modest and focus on the demonstrated operational pattern.
8. **“Public repository leaks private material.”** Current and history scans are clean; ignored `.env` is excluded from both Git and gcloud upload. Remote content still requires an anonymous post-push scan.
9. **“Production-ready is overstated.”** README limitations prevent this. Do not describe the MVP as production deployed in a real organization.
10. **Greatest remaining risk:** a rushed or unclear final recording. The implementation evidence is stronger than the current absence of a video; human recording quality is now the decisive gap.

No product change is justified by this review. Only presentation discipline remains.
