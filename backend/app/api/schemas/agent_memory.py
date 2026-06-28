# -*- coding: utf-8 -*-
"""AgentMemory API Schemas。"""

from datetime import datetime

from pydantic import BaseModel, Field


class AgentMemoryCreate(BaseModel):
    content: str = Field(default="", description="记忆内容")


class AgentMemoryUpdate(BaseModel):
    content: str | None = Field(default=None, description="记忆内容")


class AgentMemoryReorder(BaseModel):
    memory_ids: list[str] = Field(description="按新顺序排列的记忆 ID 列表")


class AgentMemoryResponse(BaseModel):
    id: str
    content: str
    order_index: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentMemoryListResponse(BaseModel):
    items: list[AgentMemoryResponse]
    total: int
    page: int
    page_size: int
