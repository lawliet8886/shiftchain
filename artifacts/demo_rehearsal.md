# ShiftChain live demo rehearsal

Format: one continuous live Cloud run, normal speed, no cuts, no reset in the middle. Target: **3:35**, with a hard internal ceiling of **3:45**. The official submission limit is four minutes.

The presenter clicks only Reset Demo and EVT-001 through EVT-004. After EVT-004 there are **zero clicks**: Cloud Tasks must wake the workflow, the business effect must verify, the controlled acknowledgement loss must return HTTP 503, and the native retry must finish as `NO_OP_VERIFIED`.

## Before recording

- Use a 1440 × 900 browser viewport at 100% zoom.
- Open the deployed `.run.app` URL with the address bar visible.
- Confirm `Reliability proof: ON`, `/health` 200, queue depth 0, and no pending tasks from an earlier run.
- Start from a new Reset Demo run; never reuse a rehearsal run for the final take.
- Keep the browser console and terminals closed. No key, token, project IAM view, or secret value appears.

## Definitive English script

| Time | Visible action and evidence | Narration |
|---|---|---|
| 0:00–0:15 | Show the app immediately: Event Stream, Responsibility Journey and `.run.app` address. Click **Reset Demo**. | “A shift handoff is easy. A handoff of a handoff is where responsibility gets lost. ShiftChain keeps a verifiable custody chain while human decisions arrive over time.” |
| 0:15–0:42 | Click **Deliver EVT-001**. Keep Maya → Liam centered while Gemini processes. | “This human message says Maya handed responsibility to Liam. Gemini extracts a bounded intent; deterministic code validates and applies it; Firestore readback is required before the edge turns green.” |
| 0:42–1:08 | Click **Deliver EVT-002**. Show Maya → Liam → Sofia and schedule v2. | “Now Liam transfers what he actually received to Sofia. This second change is legal only because the first custody edge exists. The agent resolves that dependency instead of treating the messages independently.” |
| 1:08–1:35 | Click **Deliver EVT-003**. Show the dashed amber Noah → Emma edge. | “Noah requests another transfer, but Emma has not confirmed. ShiftChain persists `WAITING_CONFIRMATION` and schedules a real Cloud Task. Waiting is a safe state, not an error.” |
| 1:35–1:55 | Let g1 wake. Point to Agent Activity: initial wake, condition not met, safe no-op. | “The first wake happens before consent exists. It reads durable state, changes nothing, and waits safely.” |
| 1:55–2:18 | Click **Deliver EVT-004**. Point to Confirmation received and Resume scheduled. Then take hands off input. | “Emma confirms. Gemini interprets that message and generation two is scheduled. From this point on, I do nothing.” |
| 2:18–2:42 | Zero clicks. Show Workflow resumed automatically, solid green Noah → Emma, APPLIED then VERIFIED. | “Cloud Tasks calls the authenticated OIDC handler. ShiftChain revalidates persistent state, applies Noah to Emma, and independently verifies the result.” |
| 2:42–3:05 | Still zero clicks. Show HTTP 503, retry, unchanged versions and `NO_OP_VERIFIED`. | “Judge Mode now loses one acknowledgement after verification. The same task returns. Instead of repeating the mutation, ShiftChain reads before repeat, proves the existing effect, and keeps versions unchanged.” |
| 3:05–3:28 | Keep the complete one-screen proof visible; briefly point to the stack badges and evidence panel. | “Gemini understands intent. Deterministic code controls mutation. Firestore holds truth. Cloud Tasks handles time. Cloud Run hosts the real agent and interface.” |
| 3:28–3:35 | Hold the final custody graph and `.run.app` URL. | “Responsibility moves. ShiftChain keeps the truth.” |

## Latency plan

Five real rehearsals completed in 91.787–128.857 seconds from reset through observed `NO_OP_VERIFIED`, averaging 107.953 seconds. The script intentionally narrates architecture and custody semantics during real Gemini and scheduling latency; it does not simulate, skip, or speed up backend work. The remaining margin covers browser interaction and a slow run while remaining below 3:45.

## Failure rule

If any expected state, custody edge, HTTP 503, retry, unchanged version, or `NO_OP_VERIFIED` evidence is absent, stop the take and record it as failed. Do not reset mid-take and do not represent a partial run as successful.
