# -*- coding: utf-8 -*-
"""
Volume 数据模型。
"""

from datetime import UTC, datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class Volume(SQLModel, table=True):
    """小说卷模型。"""

    __tablename__ = "volumes"
    __table_args__ = (
        UniqueConstraint("project_id", "order", name="uq_volumes_project_order"),
    )

    id: str = Field(default_factory=generate_id, primary_key=True)
    project_id: str = Field(index=True, foreign_key="projects.id")
    title: str = Field(max_length=200)
    description: str | None = Field(default=None)
    order: int = Field(index=True)
    chapter_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
