# -*- coding: utf-8 -*-
"""Character 数据模型。"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class Character(SQLModel, table=True):
    """项目角色模型。"""

    __tablename__ = "characters"

    id: str = Field(default_factory=generate_id, primary_key=True)
    project_id: str = Field(index=True, foreign_key="projects.id")
    name: str = Field(max_length=200)
    description: str = Field(default="")
    image_path: str | None = Field(default=None)
    is_favorited: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
