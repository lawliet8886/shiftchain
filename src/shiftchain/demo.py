from __future__ import annotations

import json

from shiftchain.engine import ReconciliationEngine
from shiftchain.frozen_data import frozen_repository, intent_for


def run_demo() -> dict:
    repository = frozen_repository()
    engine = ReconciliationEngine(repository)
    results = []
    for event_id in ("EVT-001", "EVT-002", "EVT-003", "EVT-004", "AMB-001"):
        result = engine.process(event_id, intent_for(event_id))
        results.append(result.model_dump(mode="json"))
    custody = [entry.to_worker_id for entry in repository.custody_chain("SHF-260826-E")]
    run = repository.get_run("RUN-DEMO-001")
    return {
        "tagline": "Responsibility moves. ShiftChain keeps the truth.",
        "results": results,
        "custody_SHF_260826_E": custody,
        "final_owner": run.shifts["SHF-260826-E"].current_owner_id if run else None,
        "schedule_version": run.schedule_version if run else None,
    }


def main() -> None:
    print(json.dumps(run_demo(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

