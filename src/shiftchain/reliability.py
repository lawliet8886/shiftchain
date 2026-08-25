from __future__ import annotations

from dataclasses import dataclass


LOST_ACK_AFTER_VERIFY_ONCE = "LOST_ACK_AFTER_VERIFY_ONCE"


@dataclass(frozen=True)
class NoOpVerificationResult:
    verified: bool
    evidence_id: str | None
    errors: tuple[str, ...]
    observed_owner_id: str | None = None
    observed_shift_version: int | None = None
    observed_schedule_version: int | None = None
    custody_head_event_id: str | None = None

