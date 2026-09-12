# -*- coding: utf-8 -*-
"""AgentMemory API Schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class AgentMemoryCreate(BaseModel):
    content: str = Field(default="", description="Isi catatan memori")


class AgentMemoryUpdate(BaseModel):
    content: str | None = Field(default=None, description="Isi catatan memori")


class AgentMemoryReorder(BaseModel):
    memory_ids: list[str] = Field(description="Daftar ID catatan memori dalam urutan baru")


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
