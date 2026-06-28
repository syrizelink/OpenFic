# -*- coding: utf-8 -*-
"""
Revision 数据模型 - 项目级版本记录。
"""

from datetime import UTC, datetime

from sqlalchemy import Column, ForeignKey, String
from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class Revision(SQLModel, table=True):
    """
    项目级版本记录。

    一个 Revision 代表用户消息触发的一轮 Agent 交互，
    可能涉及零到多个章节的修改（通过 Commits 记录）。

    Revision 是用户可见的业务版本点；回滚会创建新的 rollback revision，
    不修改历史 revision。
    """

    __tablename__ = "revisions"

    id: str = Field(default_factory=generate_id, primary_key=True)
    project_id: str = Field(index=True, foreign_key="projects.id")

    message: str = Field(description="版本描述/操作说明")
    agent_session_id: str | None = Field(
        default=None, description="关联的 Agent 会话 ID"
    )

    status: str = Field(
        default="active",
        index=True,
        description="Revision 状态: active/interrupted/completed/failed/cancelled/rollback",
    )
    revision_type: str = Field(
        default="manual", index=True, description="Revision 类型: agent/manual/rollback"
    )
    parent_revision_id: str | None = Field(
        default=None, index=True, foreign_key="revisions.id"
    )
    task_id: str | None = Field(
        default=None,
        sa_column=Column(
            String,
            ForeignKey("tasks.id", use_alter=True, name="fk_revisions_task_id_tasks"),
            nullable=True,
            index=True,
        ),
    )
    user_message_id: str | None = Field(
        default=None,
        index=True,
        description="触发该 revision 的用户消息 ID",
    )
    user_message_seq: int | None = Field(
        default=None,
        index=True,
        description="触发该 revision 的用户消息 seq",
    )
    pre_run_checkpoint_id: str | None = Field(
        default=None,
        index=True,
        description="用户消息发送前的 LangGraph checkpoint_id",
    )
    graph_thread_id: str | None = Field(
        default=None,
        index=True,
        description="LangGraph thread_id",
    )
    is_checkpoint: bool = Field(
        default=False, index=True, description="是否为用户可见的检查点"
    )

    project_snapshot_title: str = Field(max_length=200)
    project_snapshot_description: str | None = Field(default=None)
    project_snapshot_word_count: int = Field(default=0)
    project_snapshot_chapter_count: int = Field(default=0)

    started_at: datetime | None = Field(default=None, index=True)
    finished_at: datetime | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
