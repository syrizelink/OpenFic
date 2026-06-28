# -*- coding: utf-8 -*-
"""AgentMemory 数据模型 - 用户偏好记忆。"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class AgentMemory(SQLModel, table=True):
    """用户偏好记忆。"""

    __tablename__ = "agent_memories"

    id: str = Field(default_factory=generate_id, primary_key=True)
    content: str = Field(default="")
    order_index: int = Field(default=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
