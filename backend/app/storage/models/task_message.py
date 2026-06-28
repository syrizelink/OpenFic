# -*- coding: utf-8 -*-
"""TaskMessage 数据模型。"""

from datetime import UTC, datetime

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class TaskMessage(SQLModel, table=True):
    """任务消息模型。"""

    __tablename__ = "task_messages"

    id: str = Field(default_factory=generate_id, primary_key=True)
    task_id: str = Field(index=True, foreign_key="tasks.id")
    role: str = Field(max_length=20, index=True)
    agent_id: str | None = Field(default=None, max_length=50, index=True)
    content: str = Field(default="")
    tool_calls: str = Field(default="[]")
    tool_call_id: str | None = Field(default=None, index=True)
    message_metadata: str = Field(
        default="{}",
        sa_column=Column("metadata", Text, nullable=False, default="{}"),
    )
    message_type: str | None = Field(default=None, index=True)
    message_status: str | None = Field(default=None, index=True)
    display_channel: str | None = Field(default=None, index=True)
    payload: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    correlation_id: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
