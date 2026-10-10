# -*- coding: utf-8 -*-
"""Persistent audit records for every LLM invocation."""

from datetime import UTC, datetime

from sqlalchemy import Connection, Index, event
from sqlalchemy.orm import Mapper
from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class LLMAuditLog(SQLModel, table=True):
    """Stores the request, response, usage, and outcome of one LLM call."""

    __tablename__ = "agent_audit_logs"
    # Dashboard queries read metadata without scanning rows containing long prompts.
    __table_args__ = (
        Index(
            "ix_agent_audit_logs_dashboard_metrics",
            "created_at",
            "id",
            "project_id",
            "model_id",
            "model_name",
            "tokens_input",
            "tokens_output",
            "tokens_total",
            "latency_ms",
            "first_token_ms",
            "status",
            "model_provider",
            "category",
            "operation",
        ),
        Index("ix_agent_audit_logs_model_id_model_name", "model_id", "model_name"),
        Index("ix_agent_audit_logs_detail_storage", "has_details", "detail_bytes"),
    )

    id: str = Field(default_factory=generate_id, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)

    task_id: str | None = Field(default=None, index=True, foreign_key="tasks.id")
    session_id: str | None = Field(default=None, index=True)
    parent_session_id: str | None = Field(default=None, index=True)
    child_run_id: str | None = Field(default=None, index=True)
    project_id: str = Field(index=True, foreign_key="projects.id")
    chapter_id: str | None = Field(default=None, index=True, foreign_key="chapters.id")
    revision_id: str | None = Field(
        default=None, index=True, foreign_key="revisions.id"
    )

    category: str = Field(default="agent", max_length=50, index=True)
    operation: str = Field(max_length=50, index=True)
    call_sequence: int | None = Field(default=None)

    model_id: str = Field(index=True)
    model_provider: str | None = Field(default=None, max_length=50, index=True)
    model_name: str | None = Field(default=None, max_length=100)

    request_messages: str | None = Field(default=None)
    tool_references: str | None = Field(default=None)
    response_content: str | None = Field(default=None)
    response_tool_calls: str | None = Field(default=None)
    tool_call_results: str | None = Field(default=None)

    tokens_input: int = Field(default=0)
    tokens_output: int = Field(default=0)
    tokens_total: int = Field(default=0)
    token_cache: int = Field(default=0)

    latency_ms: int | None = Field(default=None)
    first_token_ms: int | None = Field(default=None)

    status: str = Field(max_length=20, index=True)
    error_type: str | None = Field(default=None, max_length=50)
    error_message: str | None = Field(default=None)
    error_status_code: int | None = Field(default=None)

    tool_calls_count: int = Field(default=0)
    tool_calls_success_count: int = Field(default=0)
    tool_calls_failed_count: int = Field(default=0)

    extra_data: str | None = Field(default=None)

    has_details: bool = Field(default=False)
    detail_bytes: int = Field(default=0)

    def sync_detail_storage_metadata(self) -> None:
        """Refresh the denormalized metadata used by storage overview queries."""
        detail_values = (
            self.request_messages,
            self.tool_references,
            self.response_content,
            self.response_tool_calls,
            self.tool_call_results,
            self.extra_data,
        )
        self.has_details = any(value is not None for value in detail_values)
        self.detail_bytes = sum(
            len(value.encode("utf-8"))
            for value in detail_values
            if value is not None
        )

    def clear_detail_storage_metadata(self) -> None:
        """Reset the denormalized metadata after detail payloads are removed."""
        self.has_details = False
        self.detail_bytes = 0


def _sync_detail_storage_metadata(
    _mapper: Mapper[LLMAuditLog],
    _connection: Connection,
    target: LLMAuditLog,
) -> None:
    target.sync_detail_storage_metadata()


event.listen(LLMAuditLog, "before_insert", _sync_detail_storage_metadata)
event.listen(LLMAuditLog, "before_update", _sync_detail_storage_metadata)
