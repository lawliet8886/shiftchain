from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CloudConfig:
    project_id: str
    region: str
    firestore_database: str
    queue_name: str
    task_caller_email: str
    service_base_url: str
    task_audience: str
    demo_delay_seconds: int

    @classmethod
    def from_env(cls) -> "CloudConfig":
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
        region = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")
        service_base_url = os.environ.get("SHIFTCHAIN_SERVICE_URL", "").rstrip("/")
        audience = os.environ.get("SHIFTCHAIN_TASK_AUDIENCE", service_base_url).rstrip("/")
        task_caller = os.environ.get("SHIFTCHAIN_TASK_CALLER_EMAIL", "")
        missing = [
            name
            for name, value in (
                ("GOOGLE_CLOUD_PROJECT", project_id),
                ("SHIFTCHAIN_SERVICE_URL", service_base_url),
                ("SHIFTCHAIN_TASK_AUDIENCE", audience),
                ("SHIFTCHAIN_TASK_CALLER_EMAIL", task_caller),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(f"Missing cloud configuration: {', '.join(missing)}")
        delay = int(os.environ.get("DEMO_DELAY_SECONDS", "15"))
        if delay < 1 or delay > 3600:
            raise RuntimeError("DEMO_DELAY_SECONDS must be between 1 and 3600")
        return cls(
            project_id=project_id,
            region=region,
            firestore_database=os.environ.get("FIRESTORE_DATABASE", "shiftchain"),
            queue_name=os.environ.get("CLOUD_TASKS_QUEUE", "shiftchain-resume"),
            task_caller_email=task_caller,
            service_base_url=service_base_url,
            task_audience=audience,
            demo_delay_seconds=delay,
        )

