# -*- coding: utf-8 -*-
"""Agent Definition API Schemas。"""

from pydantic import BaseModel, Field


class AgentDefinitionResponse(BaseModel):
    key: str
    display_name: str
    description: str = ""
    kind: str
    prompt_agent_name: str
    model_id: str | None = None
    tool_category_keys: list[str] = Field(default_factory=list)
    enabled_skill_ids: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    enabled: bool = True
    source: str = "builtin"
    delegatable_agents: list[str] = Field(default_factory=list)


class AgentDefinitionCreateRequest(BaseModel):
    key: str = Field(..., max_length=50)
    display_name: str = Field(..., max_length=200)
    description: str = Field(default="", max_length=1000)
    kind: str = Field(..., max_length=20)
    prompt_agent_name: str = Field(..., max_length=50)
    model_id: str | None = Field(default=None, max_length=100)
    tool_category_keys: list[str] = Field(default_factory=list)
    enabled_skill_ids: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    delegatable_agents: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class AgentDefinitionUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    kind: str | None = Field(default=None, max_length=20)
    prompt_agent_name: str | None = Field(default=None, max_length=50)
    model_id: str | None = Field(default=None, max_length=100)
    tool_category_keys: list[str] | None = None
    enabled_skill_ids: list[str] | None = None
    metadata: dict | None = None
    enabled: bool | None = None
    delegatable_agents: list[str] | None = None

    model_config = {"extra": "forbid"}


class AgentDefinitionListResponse(BaseModel):
    definitions: list[AgentDefinitionResponse]


class AgentToolCategoryResponse(BaseModel):
    key: str
    name: str
    tool_keys: list[str] = Field(default_factory=list)


class AgentToolCategoryListResponse(BaseModel):
    categories: list[AgentToolCategoryResponse]
