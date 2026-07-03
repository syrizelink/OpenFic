"""AgentRunMessage SQLModel 表。"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import CheckConstraint, Column, Index, JSON, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class AgentRunMessage(SQLModel, table=True):
    """Agent 运行时持久化的消息。"""

    __tablename__ = "agent_run_messages"

    id: str = Field(default_factory=generate_id, primary_key=True)
    session_id: str = Field(index=True, max_length=64)
    task_id: str = Field(index=True, foreign_key="tasks.id", max_length=64)
    project_id: str = Field(index=True, default="", max_length=64)
    role: str = Field(max_length=20, index=True)
    agent_id: str | None = Field(default=None, max_length=50, index=True)
    content: str = Field(default="", sa_column=Column(Text, nullable=False, default=""))
    reasoning: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    reasoning_duration_ms: int | None = Field(default=None)
    tool_calls: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    tool_call_id: str | None = Field(default=None, max_length=64, index=True)
    tool_name: str | None = Field(default=None, max_length=64)
    status: str = Field(max_length=20, index=True)
    message_type: str = Field(default="message", max_length=50, index=True)
    display_channel: str = Field(default="list", max_length=20, index=True)
    llm_visibility: str = Field(default="visible", max_length=20, index=True)
    seq: int = Field(index=True, ge=0)
    message_metadata: str = Field(
        default="{}",
        sa_column=Column("metadata", Text, nullable=False, default="{}"),
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentContextCompaction(SQLModel, table=True):
    """Agent context compaction range persisted per session."""

    __tablename__ = "agent_context_compactions"
    __table_args__ = (
        CheckConstraint(
            "start_seq >= 0",
            name="ck_agent_context_compactions_start_seq_nonnegative",
        ),
        CheckConstraint(
            "end_seq >= 0",
            name="ck_agent_context_compactions_end_seq_nonnegative",
        ),
        CheckConstraint(
            "source_input_tokens >= 0",
            name="ck_agent_context_compactions_source_input_tokens_nonnegative",
        ),
        CheckConstraint(
            "summary_tokens >= 0",
            name="ck_agent_context_compactions_summary_tokens_nonnegative",
        ),
        CheckConstraint(
            "start_seq <= end_seq",
            name="ck_agent_context_compactions_valid_range",
        ),
        Index(
            "ix_agent_context_compactions_session_start_end",
            "session_id",
            "start_seq",
            "end_seq",
        ),
    )

    id: str = Field(default_factory=generate_id, primary_key=True)
    session_id: str = Field(index=True, max_length=64)
    task_id: str = Field(index=True, foreign_key="tasks.id", max_length=64)
    project_id: str = Field(index=True, default="", max_length=64)
    start_seq: int = Field(index=True, ge=0)
    end_seq: int = Field(index=True, ge=0)
    summary: str = Field(sa_column=Column(Text, nullable=False))
    trigger: str = Field(index=True, max_length=20)
    source_input_tokens: int = Field(default=0, ge=0)
    summary_tokens: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)


class AgentDefinitionRecord(SQLModel, table=True):
    """DB-backed PA/SA agent definition override/default row."""

    __tablename__ = "agent_definitions"

    id: str = Field(default_factory=generate_id, primary_key=True)
    key: str = Field(index=True, unique=True, max_length=50)
    display_name: str = Field(max_length=200)
    description: str = Field(default="", sa_column=Column(Text, nullable=False, default=""))
    kind: str = Field(index=True, max_length=20)
    prompt_agent_name: str = Field(max_length=50)
    model_id: str | None = Field(default=None, max_length=100)
    tool_category_keys_json: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False, default=list),
    )
    enabled_skill_ids_json: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False, default=list),
    )
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, default=dict),
    )
    enabled: bool = Field(default=True, index=True)
    order_index: int = Field(default=0, index=True)
    source: str = Field(default="builtin", max_length=20, index=True)
    delegatable_agents: list[str] = Field(
        default_factory=list,
        sa_column=Column("delegatable_agents", JSON, nullable=False, default=list),
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentChildRun(SQLModel, table=True):
    """Child LangGraph run tracked under a parent agent session."""

    __tablename__ = "agent_child_runs"

    id: str = Field(default_factory=generate_id, primary_key=True)
    parent_session_id: str = Field(index=True, max_length=64)
    parent_task_id: str = Field(index=True, foreign_key="tasks.id", max_length=64)
    parent_thread_id: str = Field(index=True, max_length=128)
    child_thread_id: str = Field(index=True, max_length=128)
    agent_key: str = Field(index=True, max_length=50)
    dispatch_id: str = Field(index=True, max_length=64)
    tool_call_id: str = Field(index=True, max_length=64)
    status: str = Field(default="queued", index=True, max_length=20)
    is_active: bool = Field(default=True, index=True)
    request_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, default=dict),
    )
    result_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    pending_approval_id: str | None = Field(default=None, index=True, max_length=128)
    pending_approval_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    recycled_at: datetime | None = Field(default=None, index=True)
    last_assistant_content: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )
    last_user_message_at: datetime | None = Field(default=None, index=True)
    last_completed_at: datetime | None = Field(default=None, index=True)
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, default=dict),
    )
    parent_revision_id: str | None = Field(default=None, index=True, max_length=64)
    started_at: datetime | None = Field(default=None, index=True)
    completed_at: datetime | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentChildRunRequest(SQLModel, table=True):
    """Queued turn request bound to a persistent child thread."""

    __tablename__ = "agent_child_run_requests"

    id: str = Field(default_factory=generate_id, primary_key=True)
    child_run_id: str = Field(index=True, foreign_key="agent_child_runs.id", max_length=64)
    parent_session_id: str = Field(index=True, max_length=64)
    parent_task_id: str = Field(index=True, foreign_key="tasks.id", max_length=64)
    request_kind: str = Field(index=True, max_length=50)
    content: str = Field(default="", sa_column=Column(Text, nullable=False, default=""))
    status: str = Field(default="pending", index=True, max_length=20)
    assistant_content: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )
    error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    parent_revision_id: str | None = Field(default=None, index=True, max_length=64)
    child_user_message_id: str | None = Field(default=None, index=True, max_length=64)
    child_user_message_seq: int | None = Field(default=None, index=True)
    pre_request_checkpoint_id: str | None = Field(default=None, index=True, max_length=128)
    seq: int = Field(index=True, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    started_at: datetime | None = Field(default=None, index=True)
    completed_at: datetime | None = Field(default=None, index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PlanRecord(SQLModel, table=True):
    """Shared plan row scoped to one parent/subagent session tree."""

    __tablename__ = "plans"

    id: str = Field(default_factory=generate_id, primary_key=True)
    scope_id: str = Field(index=True, max_length=64)
    topic: str = Field(max_length=200)
    description: str = Field(default="", sa_column=Column(Text, nullable=False, default=""))
    status: str = Field(default="pending", index=True, max_length=20)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PlanTodoRecord(SQLModel, table=True):
    """Ordered todo row under one shared plan."""

    __tablename__ = "plan_todos"
    __table_args__ = (
        UniqueConstraint(
            "plan_id",
            "sort_index",
            name="uq_plan_todos_plan_id_sort_index",
        ),
    )

    id: str = Field(default_factory=generate_id, primary_key=True)
    plan_id: str = Field(index=True, foreign_key="plans.id", max_length=64)
    title: str = Field(default="", sa_column=Column(Text, nullable=False, default=""))
    content: str = Field(default="", sa_column=Column(Text, nullable=False, default=""))
    status: str = Field(default="pending", index=True, max_length=20)
    sort_index: int = Field(index=True, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
