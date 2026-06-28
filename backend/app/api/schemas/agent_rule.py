# -*- coding: utf-8 -*-
"""AgentRule API Schemas。"""

from datetime import datetime

from pydantic import BaseModel, Field


class AgentRuleCreate(BaseModel):
    title: str = Field(default="", description="规则标题")
    content: str = Field(default="", description="规则内容")


class AgentRuleUpdate(BaseModel):
    title: str | None = Field(default=None, description="规则标题")
    content: str | None = Field(default=None, description="规则内容")


class AgentRuleReorder(BaseModel):
    rule_ids: list[str] = Field(description="按新顺序排列的规则 ID 列表")


class AgentRuleResponse(BaseModel):
    id: str
    title: str
    content: str
    order_index: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentRuleListResponse(BaseModel):
    items: list[AgentRuleResponse]
    total: int
    page: int
    page_size: int
