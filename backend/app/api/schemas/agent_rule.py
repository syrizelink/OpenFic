# -*- coding: utf-8 -*-
"""AgentRule API Schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class AgentRuleCreate(BaseModel):
    title: str = Field(default="", description="Judul aturan")
    content: str = Field(default="", description="Isi aturan")
    scope: str = Field(default="global", description="Cakupan: global atau project")
    project_id: str | None = Field(default=None, description="ID proyek yang terkait dengan cakupan project")


class AgentRuleUpdate(BaseModel):
    title: str | None = Field(default=None, description="Judul aturan")
    content: str | None = Field(default=None, description="Isi aturan")


class AgentRuleReorder(BaseModel):
    rule_ids: list[str] = Field(description="Daftar ID aturan dalam urutan baru")


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