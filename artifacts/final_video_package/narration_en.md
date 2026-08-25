# Final English narration

Target: **3:35–3:42** at a calm natural pace. One continuous 1× live run.

## 0:00–0:18 — Friction

“A shift handoff is simple. A handoff of a handoff is where responsibility starts getting lost. ShiftChain turns those human messages into a verified custody chain, even when approval arrives later and infrastructure delivers the same task again.”

## 0:18–0:45 — EVT-001

“Maya hands responsibility to Liam. Gemini interprets that message into a bounded intent, but it cannot mutate the schedule. Deterministic validation checks the current owner, applies the change, and requires Firestore readback before this edge becomes verified.”

## 0:45–1:10 — EVT-002

“Now Liam hands the same responsibility to Sofia. This is not an independent update: Liam can transfer it only because the earlier Maya-to-Liam custody edge exists. ShiftChain preserves the full temporal chain instead of overwriting the latest name.”

## 1:10–1:35 — EVT-003

“The second chain is different. Noah requests a transfer to Emma, but Emma has not confirmed. The agent persists a waiting state and schedules a real Cloud Task. Waiting is safe, visible, and durable—not an error and not process memory.”

## 1:35–1:55 — Early wake

“Generation one wakes before consent exists. It reads the persistent condition, makes no business change, and exits safely. The workflow remains ready for a fact that may arrive later.”

## 1:55–2:20 — EVT-004

“Emma confirms. Gemini interprets that message; the confirmation is persisted and generation two is scheduled. From this point on, I will not click anything.”

## 2:20–2:42 — Autonomous resume

“Cloud Tasks calls the internal handler with its dedicated OIDC identity. ShiftChain revalidates persistent state, applies Noah to Emma, and independently verifies the custody edge. The workflow completed itself after the human fact arrived.”

## 2:42–3:08 — Reliability

“Judge Mode now intentionally simulates one lost acknowledgement after the business effect is verified. The handler returns HTTP 503, so the same Cloud Task retries. ShiftChain reads before repeating, finds the existing effect, verifies the unchanged versions and custody, and records `NO_OP_VERIFIED` instead of mutating twice.”

## 3:08–3:30 — Architecture

“Gemini understands intent. Google ADK coordinates bounded tools. Deterministic code controls mutation. Firestore holds truth. Cloud Tasks controls time. Readback proves the outcome. The Gemini credential remains in Secret Manager.”

## 3:30–3:38 — Cloud proof and closing

“This is the live Google Cloud Run application at its public dot-run-app URL. Responsibility moves. ShiftChain keeps the truth.”

## Delivery notes

- Describe the visible state; never say “AI thinking.”
- Continue narration through real Gemini latency.
- Pause briefly after “I will not click anything” so the zero-click boundary is obvious.
- Say that the HTTP 503 is intentional before it appears.
- Do not claim production use, exactly-once infrastructure, or unrestricted domain support.
