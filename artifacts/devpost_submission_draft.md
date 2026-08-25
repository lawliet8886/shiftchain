# ShiftChain — Devpost submission draft

**Category:** Taskmaster  
**Video URL:** PENDING HUMAN UPLOAD

## One-liner

An autonomous agent that reconciles chained responsibility handoffs, waits for late consent, resumes itself, and verifies every change.

## Inspiration

A shift handoff is simple. A handoff of a handoff is where responsibility starts getting lost. Human responsibility changes arrive as messy events, depend on earlier transfers, and may wait on approvals that arrive later. We wanted the system—not a person watching a dashboard—to preserve that history and finish the work safely.

## What it does

ShiftChain turns human handoff messages into verified changes to operational responsibility.

It interprets a message, validates who can transfer responsibility, preserves a temporal custody chain, waits when consent is missing, schedules its own wake-up, resumes after confirmation, mutates persistent state, and independently verifies the result.

The live story follows two chains:

- Maya → Liam → Sofia proves that a later handoff depends on a real earlier custody edge.
- Noah → Emma proves durable waiting, an early safe no-op, late confirmation, and autonomous Cloud Tasks resume.

Judge Mode then intentionally simulates one lost acknowledgement after the verified business effect. The same Cloud Task retries. ShiftChain reads before repeating, detects the existing effect, verifies it, and returns `NO_OP_VERIFIED` with versions unchanged.

## How we built it

Gemini 3.7 Flash performs bounded intent extraction from the four frozen human messages. A single Google ADK agent coordinates narrowly scoped tools. Gemini never receives authority to mutate operational truth.

Deterministic Python code enforces worker, request, schedule-version and custody preconditions. Cloud Firestore stores requests, shifts, schedules, confirmations, generations and an append-only custody ledger. Google Cloud Tasks handles delayed OIDC-authenticated wake-ups and native retries. FastAPI and the one-screen judge interface run on Google Cloud Run; the Gemini credential is supplied through Secret Manager.

**Gemini understands intent. Deterministic code controls mutation. Firestore holds truth. Cloud Tasks controls time. Readback proves the outcome.**

## The autonomous workflow

1. EVT-001 transfers Maya → Liam and verifies the new custody edge.
2. EVT-002 transfers Liam → Sofia only because Liam really received custody.
3. EVT-003 requests Noah → Emma, but confirmation is absent, so the agent persists `WAITING_CONFIRMATION` and schedules generation one.
4. The first wake finds no confirmation and safely changes nothing.
5. EVT-004 persists Emma's confirmation and schedules generation two.
6. With no further click, Cloud Tasks wakes ShiftChain, which revalidates, applies and verifies Noah → Emma.

## Reliability

Cloud Tasks provides at-least-once delivery, so ShiftChain does not pretend infrastructure delivery is exactly once. After the verified Noah → Emma mutation, Judge Mode deliberately returns one HTTP 503 to model a lost acknowledgement. The native retry performs a persistent read-before-repeat check covering the request, intent, ledger, owner, schedule, version and custody head. It creates no second business mutation and records deterministic `NO_OP_VERIFIED` evidence.

Five consecutive real-cloud rehearsals completed successfully, with zero duplicate versions or custody edges.

## Challenges we ran into

Our first cloud design assumed Gemini would process the confirmation before a 15-second scheduled wake. Real model latency invalidated that assumption. We redesigned the workflow around durable generations: an early wake is a safe no-op, and confirmation arriving later schedules a new generation that resumes autonomously.

We also separated provider success from business success. `APPLIED` is not `VERIFIED`, and an HTTP acknowledgement is not proof of the business outcome.

## Accomplishments

- A real autonomous delayed resume through an OIDC-authenticated Cloud Task.
- Persistent custody and version preconditions in a named Firestore database.
- Real native retry after an intentional post-verification HTTP 503.
- Exactly one business mutation and `NO_OP_VERIFIED` on the retry.
- Five of five complete real-cloud rehearsals successful.
- A one-screen interface that makes custody, waiting, resume and reliability visible.

## What we learned

Exactly-once business effects cannot be assumed from at-least-once infrastructure delivery.

An LLM should interpret intent, not own authority to mutate operational truth.

Long-running agent workflows must be independent of model latency, process memory and any presenter remaining online.

## What's next

The frozen MVP uses synthetic events and one week of responsibility context. The same custody pattern could later serve field teams, hospitality operations, equipment custody, volunteer operations, security handoffs and on-call rotations. Those integrations are future work, not part of this submission.

## Built with

- Gemini 3.7 Flash
- Google ADK
- Google GenAI SDK
- Google Cloud Run
- Cloud Firestore
- Google Cloud Tasks
- Google Secret Manager
- FastAPI
- Python

## Google Cloud proof

ShiftChain is deployed on Google Cloud Run. Persistent state and the temporal custody ledger are stored in Firestore. Cloud Tasks performs OIDC-authenticated asynchronous resume and native retries.

## Data and limitations

All organization, worker, shift and message data are synthetic. The MVP uses four frozen demo events and a one-week context; it does not generate schedules, process payroll, integrate with production HR systems, support arbitrary out-of-order events, or expose open-ended chat.

## Links

- Hosted app: https://shiftchain-demo-7skxzw642a-uc.a.run.app
- Source: https://github.com/lawliet8886/shiftchain
- Architecture: https://github.com/lawliet8886/shiftchain/blob/main/docs/architecture.svg
- Video: PENDING HUMAN UPLOAD
