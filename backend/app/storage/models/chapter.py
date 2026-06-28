# -*- coding: utf-8 -*-
"""
Chapter 数据模型。
"""

from datetime import UTC, datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class Chapter(SQLModel, table=True):
    """
    小说章节模型。

    Attributes:
        id: 章节唯一标识符（nanoid）。
        project_id: 所属项目 ID。
        title: 章节标题。
        content: 章节正文内容。
        word_count: 章节字数，默认为 0。
        order: 排序序号。
        created_at: 创建时间。
        updated_at: 上次修改时间。
    """

    __tablename__ = "chapters"
    __table_args__ = (
        UniqueConstraint("volume_id", "order", name="uq_chapters_volume_order"),
    )

    id: str = Field(default_factory=generate_id, primary_key=True)
    project_id: str = Field(index=True, foreign_key="projects.id")
    volume_id: str = Field(index=True, foreign_key="volumes.id")
    title: str = Field(max_length=200)
    content: str = Field(default="")
    word_count: int = Field(default=0)
    order: int = Field(index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
