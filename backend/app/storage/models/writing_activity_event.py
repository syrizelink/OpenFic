# -*- coding: utf-8 -*-
"""
Writing Activity Event 数据模型 - 写作活动事件。
"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class WritingActivityEvent(SQLModel, table=True):
    """记录章节内容变更产生的字数快照事件。"""

    __tablename__ = "writing_activity_events"

    id: str = Field(default_factory=generate_id, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)

    project_id: str = Field(index=True)
    chapter_id: str | None = Field(default=None, index=True)
    chapter_title: str | None = Field(default=None, max_length=200)

    source: str = Field(max_length=30, index=True)
    operation: str = Field(max_length=30, index=True)

    old_word_count: int = Field(default=0)
    new_word_count: int = Field(default=0)
    word_delta: int = Field(default=0)

    revision_id: str | None = Field(default=None, index=True)
    task_id: str | None = Field(default=None, index=True)
    agent_session_id: str | None = Field(default=None, index=True)
