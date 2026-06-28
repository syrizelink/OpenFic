# -*- coding: utf-8 -*-
"""
Setting 数据模型。
"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class Setting(SQLModel, table=True):
    """
    用户设置模型，存储键值对形式的配置。

    Attributes:
        id: 设置唯一标识符（nanoid）。
        key: 设置键名，唯一索引。
        value: 设置值，JSON 格式字符串。
        created_at: 创建时间。
        updated_at: 上次修改时间。
    """

    __tablename__ = "settings"

    id: str = Field(default_factory=generate_id, primary_key=True)
    key: str = Field(unique=True, index=True, max_length=100)
    value: str = Field(default="")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
