# -*- coding: utf-8 -*-
"""ProjectRule 数据模型 - 项目级智能体行为规则。"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class ProjectRule(SQLModel, table=True):
    """项目级智能体行为规则。"""

    __tablename__ = "project_rules"

    id: str = Field(default_factory=generate_id, primary_key=True)
    project_id: str = Field(index=True, foreign_key="projects.id")
    title: str = Field(default="")
    content: str = Field(default="")
    order_index: int = Field(default=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
