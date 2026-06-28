"""SQLModel tables for persistent background jobs and events."""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.background.jobs.states import JOB_STATUS_PENDING
from app.core.ids import generate_id


class BackgroundJob(SQLModel, table=True):
    """Persistent background job state."""

    __tablename__ = "background_jobs"

    id: str = Field(default_factory=generate_id, primary_key=True)
    type: str = Field(max_length=80, index=True)
    status: str = Field(default=JOB_STATUS_PENDING, max_length=30, index=True)
    queue: str = Field(default="default", max_length=80, index=True)
    subject_type: str | None = Field(default=None, max_length=80, index=True)
    subject_id: str | None = Field(default=None, index=True)
    payload_json: str = Field(default="{}")
    context_json: str = Field(default="{}")
    progress_json: str = Field(default="{}")
    result_json: str | None = Field(default=None)
    error_json: str | None = Field(default=None)
    attempt_count: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=1, ge=1)
    event_sequence: int = Field(default=0, ge=0)
    timeout_seconds: int | None = Field(default=None, ge=1)
    next_run_at: datetime | None = Field(default=None, index=True)
    locked_by: str | None = Field(default=None, index=True, max_length=100)
    locked_at: datetime | None = Field(default=None, index=True)
    heartbeat_at: datetime | None = Field(default=None, index=True)
    lease_expires_at: datetime | None = Field(default=None, index=True)
    cancel_requested_at: datetime | None = Field(default=None, index=True)
    cancel_reason: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    started_at: datetime | None = Field(default=None)
    finished_at: datetime | None = Field(default=None)


class BackgroundJobEvent(SQLModel, table=True):
    """Persistent event emitted by a background job."""

    __tablename__ = "background_job_events"

    id: str = Field(default_factory=generate_id, primary_key=True)
    job_id: str = Field(foreign_key="background_jobs.id", index=True)
    item_id: str | None = Field(default=None, foreign_key="background_job_items.id", index=True)
    sequence: int = Field(default=0, ge=0, index=True)
    event_type: str = Field(max_length=100, index=True)
    payload_json: str = Field(default="{}")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)


class BackgroundJobItem(SQLModel, table=True):
    """Persistent sub-item state for batch background jobs."""

    __tablename__ = "background_job_items"

    id: str = Field(default_factory=generate_id, primary_key=True)
    job_id: str = Field(foreign_key="background_jobs.id", index=True)
    item_key: str = Field(max_length=200, index=True)
    type: str = Field(max_length=80, index=True)
    status: str = Field(default=JOB_STATUS_PENDING, max_length=30, index=True)
    payload_json: str = Field(default="{}")
    result_json: str | None = Field(default=None)
    error_json: str | None = Field(default=None)
    progress_json: str = Field(default="{}")
    order_index: int = Field(default=0, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    started_at: datetime | None = Field(default=None)
    finished_at: datetime | None = Field(default=None)
