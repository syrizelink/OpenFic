# -*- coding: utf-8 -*-
"""AgentRule 数据模型 - 用户定义的智能体行为规则。"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class AgentRule(SQLModel, table=True):
    """用户定义的智能体行为规则。"""

    __tablename__ = "agent_rules"

    id: str = Field(default_factory=generate_id, primary_key=True)
    title: str = Field(default="")
    content: str = Field(default="")
    order_index: int = Field(default=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
