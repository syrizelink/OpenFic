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
    scope: str = Field(default="global", description="作用域：global 或 project")
    project_id: str | None = Field(default=None, index=True, description="project 作用域关联的项目 ID")
    token_count: int = Field(default=0, description="规则内容 Token 数")
    order_index: int = Field(default=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
