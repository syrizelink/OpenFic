# -*- coding: utf-8 -*-
"""Task 数据模型。"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class Task(SQLModel, table=True):
    """
    AI对话任务模型。

    Attributes:
        id: 任务唯一标识符（nanoid）。
        project_id: 所属项目 ID。
        title: 任务标题（取自首条用户输入，最多50字符）。
        mode: 任务模式。
        token_input: 输入 token 总数。
        token_output: 输出 token 总数。
        token_cache: 缓存命中 token 总数。
        context_input_tokens: 上一次 LLM 调用的输入 token 数。
        current_revision_id: 当前用户消息 checkpoint 对应的 revision ID。
        current_message_id: 当前最新用户消息 ID。
        agent_session_id: 关联的 Agent 会话 ID。
        is_running: 当前任务是否仍在后台运行。
        is_favorited: 是否收藏。
        created_at: 创建时间。
        updated_at: 上次修改时间。
    """

    __tablename__ = "tasks"

    id: str = Field(default_factory=generate_id, primary_key=True)
    project_id: str = Field(index=True, foreign_key="projects.id")
    title: str = Field(max_length=200)
    mode: str = Field(max_length=20, index=True)
    token_input: int = Field(default=0, ge=0)
    token_output: int = Field(default=0, ge=0)
    token_cache: int = Field(default=0, ge=0)
    context_input_tokens: int = Field(default=0, ge=0)
    current_revision_id: str | None = Field(default=None, index=True, foreign_key="revisions.id")
    current_message_id: str | None = Field(default=None, index=True)
    agent_session_id: str | None = Field(default=None, index=True, description="Agent会话ID")
    is_running: bool = Field(default=False, description="任务是否正在后台运行")
    is_favorited: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
