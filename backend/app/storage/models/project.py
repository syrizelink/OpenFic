# -*- coding: utf-8 -*-
"""
Project 数据模型。
"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class Project(SQLModel, table=True):
    """
    小说项目模型。

    Attributes:
        id: 项目唯一标识符（nanoid）。
        title: 项目标题。
        description: 项目简介，可为空。
        word_count: 统计字数，默认为 0。
        created_at: 创建时间。
        updated_at: 上次修改时间。
    """

    __tablename__ = "projects"

    id: str = Field(default_factory=generate_id, primary_key=True)
    title: str = Field(max_length=200)
    description: str | None = Field(default=None)
    word_count: int = Field(default=0)
    chapter_count: int = Field(default=0)
    cover_path: str | None = Field(default=None, description="封面图片路径")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
