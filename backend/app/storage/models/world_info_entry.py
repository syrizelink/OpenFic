# -*- coding: utf-8 -*-
"""
WorldInfoEntry 数据模型。
"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class WorldInfoEntry(SQLModel, table=True):
    """
    世界书条目模型。

    Attributes:
        id: 条目唯一标识符（nanoid）。
        world_info_id: 所属世界书 ID。
        uid: 用户可见的序列号（从 1 开始）。
        name: 条目名称。
        order: 排序序号。
        content: 条目内容。
        token_count: Token 数量。
        is_enabled: 开关状态。
        created_at: 创建时间。
        updated_at: 更新时间。
    """

    __tablename__ = "world_info_entries"

    id: str = Field(default_factory=generate_id, primary_key=True)
    world_info_id: str = Field(index=True, foreign_key="world_info.id")
    uid: int = Field(index=True)
    name: str = Field(max_length=200)
    order: int = Field(index=True)
    content: str = Field(default="")
    token_count: int = Field(default=0)
    is_enabled: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


