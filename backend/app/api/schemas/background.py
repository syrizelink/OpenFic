"""Background job API schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BackgroundJobResponse(BaseModel):
    id: str = Field(description="Job ID")
    type: str = Field(description="Job type")
    status: str = Field(description="Job status")
    queue: str
    subject_type: str | None = Field(default=None)
    subject_id: str | None = Field(default=None)
    payload: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    progress: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] = Field(default_factory=dict)
    attempt_count: int
    max_attempts: int
    timeout_seconds: int | None = Field(default=None)
    next_run_at: datetime | None = Field(default=None)
    locked_by: str | None = Field(default=None)
    locked_at: datetime | None = Field(default=None)
    heartbeat_at: datetime | None = Field(default=None)
    lease_expires_at: datetime | None = Field(default=None)
    cancel_requested_at: datetime | None = Field(default=None)
    cancel_reason: str | None = Field(default=None)
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = Field(default=None)
    finished_at: datetime | None = Field(default=None)


class BackgroundJobEventResponse(BaseModel):
    id: str
    job_id: str
    item_id: str | None = None
    sequence: int
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class BackgroundJobItemResponse(BaseModel):
    id: str
    job_id: str
    item_key: str
    type: str
    status: str
    payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] = Field(default_factory=dict)
    progress: dict[str, Any] = Field(default_factory=dict)
    order_index: int
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class BackgroundJobListResponse(BaseModel):
    items: list[BackgroundJobResponse]


class BackgroundJobEventListResponse(BaseModel):
    items: list[BackgroundJobEventResponse]


class BackgroundJobItemListResponse(BaseModel):
    items: list[BackgroundJobItemResponse]


class BackgroundCancelJobRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
