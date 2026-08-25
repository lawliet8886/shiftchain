# LinkedIn draft — do not publish

I built ShiftChain for the All Things Agentic Hackathon: an agent that reconciles chained responsibility handoffs, waits for late confirmation, resumes through Google Cloud Tasks, and verifies the resulting business state.

The reliability test is the part I care about most: after a verified change, Judge Mode intentionally returns one HTTP 503. When the same task retries, ShiftChain reads before repeating and returns `NO_OP_VERIFIED` with custody and versions unchanged.

Gemini understands intent. Deterministic code controls mutation. Firestore holds truth. Cloud Tasks handles time.

Built with Gemini 3.7 Flash, Google ADK and Google Cloud using synthetic data only.

#AllThingsAgenticHackathon
