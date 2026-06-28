# -*- coding: utf-8 -*-
"""
WorldInfo 数据模型。
"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class WorldInfo(SQLModel, table=True):
    """
    世界书模型。

    Attributes:
        id: 世界书唯一标识符（nanoid）。
        project_id: 关联的项目 ID，可选，可以为空表示未关联项目。
        name: 世界书名称。
        description: 世界书描述。
        created_at: 创建时间。
        updated_at: 更新时间。
    """

    __tablename__ = "world_info"

    id: str = Field(default_factory=generate_id, primary_key=True)
    project_id: str | None = Field(
        default=None, index=True, unique=True, foreign_key="projects.id"
    )
    name: str = Field(max_length=200)
    description: str = Field(default="")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

