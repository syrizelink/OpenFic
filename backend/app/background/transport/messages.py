"""Transport message DTOs."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class JobNotification:
    """Notification that a persisted job is ready to be processed."""

    job_id: str


@dataclass(frozen=True)
class BackgroundEventMessage:
    """Event message emitted by a worker and consumed by API/SSE bridge."""

    type: str
    job_id: str
    job_type: str
    item_id: str | None
    item_type: str | None
    subject_type: str | None
    subject_id: str | None
    payload: dict[str, Any]
    created_at: str
    project_revision: int | None = None
