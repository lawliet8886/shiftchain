from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json

from google.api_core.exceptions import AlreadyExists
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2
from pydantic import ConfigDict, BaseModel

from shiftchain.cloud_config import CloudConfig


class ResumePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    v: int = 1
    run_id: str
    target_event_id: str
    resume_generation: int
    reason: str = "WAITING_CONFIRMATION_CHECK"


@dataclass(frozen=True)
class ScheduledTask:
    name: str
    schedule_at: datetime
    already_exists: bool


def task_id_for(payload: ResumePayload) -> str:
    stable = f"{payload.run_id}|{payload.target_event_id}|{payload.resume_generation}".encode()
    return f"resume-{hashlib.sha256(stable).hexdigest()[:32]}"


class CloudTaskScheduler:
    def __init__(self, config: CloudConfig, client: tasks_v2.CloudTasksClient | None = None) -> None:
        self.config = config
        self.client = client or tasks_v2.CloudTasksClient()

    def create(self, payload: ResumePayload, delay_seconds: int | None = None) -> ScheduledTask:
        delay = self.config.demo_delay_seconds if delay_seconds is None else delay_seconds
        schedule_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
        queue_path = self.client.queue_path(
            self.config.project_id,
            self.config.region,
            self.config.queue_name,
        )
        task_name = self.client.task_path(
            self.config.project_id,
            self.config.region,
            self.config.queue_name,
            task_id_for(payload),
        )
        timestamp = timestamp_pb2.Timestamp()
        timestamp.FromDatetime(schedule_at)
        task = tasks_v2.Task(
            name=task_name,
            schedule_time=timestamp,
            http_request=tasks_v2.HttpRequest(
                http_method=tasks_v2.HttpMethod.POST,
                url=f"{self.config.service_base_url}/internal/tasks/resume",
                headers={"Content-Type": "application/json"},
                body=payload.model_dump_json().encode("utf-8"),
                oidc_token=tasks_v2.OidcToken(
                    service_account_email=self.config.task_caller_email,
                    audience=self.config.task_audience,
                ),
            ),
        )
        try:
            self.client.create_task(parent=queue_path, task=task)
            already_exists = False
        except AlreadyExists:
            already_exists = True
        return ScheduledTask(name=task_name, schedule_at=schedule_at, already_exists=already_exists)


def minimal_payload_dict(payload: ResumePayload) -> dict:
    return json.loads(payload.model_dump_json())

