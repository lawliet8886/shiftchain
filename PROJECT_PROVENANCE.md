# Project provenance

- Project: ShiftChain
- Organization: Harborlight Community Operations (HCO)
- Frozen tagline: “Responsibility moves. ShiftChain keeps the truth.”
- Phase: Phase 2 Recovery — autonomous resume proven; exact `/healthz` gate remains partial; Phase 3 not started
- Created locally: 2026-08-25, America/Sao_Paulo
- Source specification: user-provided Phase 0 freeze and Phase 1 build brief in the Codex task
- Authorized cloud project: `gen-lang-client-0643751280` (`concurso`); no other accessible project was used
- Official references consulted before implementation:
  - Gemini 3.7 Flash model: https://ai.google.dev/gemini-api/docs/models/gemini-3.7-flash
  - Google Gen AI Python SDK: https://googleapis.github.io/python-genai/
  - ADK LLM agents: https://adk.dev/agents/llm-agents/
  - ADK sessions and Runner: https://adk.dev/sessions/memory/
  - Firestore databases: https://cloud.google.com/firestore/docs/manage-databases
  - Cloud Tasks HTTP targets and OIDC: https://cloud.google.com/tasks/docs/creating-http-target-tasks
  - Cloud Run service-to-service authentication: https://cloud.google.com/run/docs/authenticating/service-to-service
  - Cloud Run known reserved URL paths: https://cloud.google.com/run/docs/known-issues
- Scope boundary: one named Firestore database, one Cloud Run service and one Cloud Tasks queue; no remote repository, custom Dockerfile, CI/CD, failure injection or Phase 3.
- Data policy: the demo organization, workers, shifts, and messages are synthetic.
