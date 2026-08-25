# ShiftChain: designing an agent that can wait, resume, and verify

> Draft only — not published. This article was created for the purpose of entering the All Things Agentic Hackathon.

A responsibility handoff is easy to read in isolation. A handoff of that handoff is harder: the second message is valid only if the first transfer actually happened. Add late consent and infrastructure retries, and a seemingly small workflow becomes a temporal reconciliation problem.

ShiftChain is a synthetic demonstration of that problem. Gemini 3.7 Flash extracts a bounded intent from a human message, while deterministic code retains authority over operational mutation. Firestore stores the durable request, version and custody history. Cloud Tasks supplies authenticated wake-ups when the workflow needs to continue later.

The most important design change came from real latency. An early version assumed confirmation would be interpreted before a 15-second task woke up. Real Gemini latency disproved that assumption. The correct design was latency-independent: an early wake reads persistent state and safely does nothing; confirmation arriving later creates a new generation that resumes autonomously.

Reliability created a second lesson. At-least-once task delivery cannot promise an exactly-once business effect by itself. ShiftChain's Judge Mode deliberately loses one acknowledgement after Noah → Emma is already verified. When the same Cloud Task returns, the system reads persistent truth before repeating anything. It finds the existing effect, verifies the versions and custody head, and records `NO_OP_VERIFIED` without a second mutation.

The architecture can be summarized in five lines:

- Gemini understands intent.
- Deterministic code controls mutation.
- Firestore holds truth.
- Cloud Tasks controls time.
- Readback proves the outcome.

All people, messages and operational data in the project are fictional. The MVP deliberately avoids real HR integrations, payroll and schedule generation so the submission can focus on one claim and prove it end to end.
