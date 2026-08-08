# -*- coding: utf-8 -*-
"""AgentRule API Schemas。"""

from datetime import datetime

from pydantic import BaseModel, Field


class AgentRuleCreate(BaseModel):
    title: str = Field(default="", description="规则标题")
    content: str = Field(default="", description="规则内容")
    scope: str = Field(default="global", description="作用域：global 或 project")
    project_id: str | None = Field(default=None, description="project 作用域关联的项目 ID")


class AgentRuleUpdate(BaseModel):
    title: str | None = Field(default=None, description="规则标题")
    content: str | None = Field(default=None, description="规则内容")


class AgentRuleReorder(BaseModel):
    rule_ids: list[str] = Field(description="按新顺序排列的规则 ID 列表")


class AgentRuleResponse(BaseModel):
    id: str
    title: str
    content: str
    scope: str
    project_id: str | None
    token_count: int
    order_index: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentRuleScopeResponse(BaseModel):
    scope: str
    project_id: str | None
    title: str
    rule_count: int


class AgentRuleScopeListResponse(BaseModel):
    items: list[AgentRuleScopeResponse]


class AgentRuleListResponse(BaseModel):
    items: list[AgentRuleResponse]
    total: int
    page: int
    page_size: int