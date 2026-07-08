# -*- coding: utf-8 -*-
"""SkillReferenceDoc API Schemas。"""

from datetime import datetime

from pydantic import BaseModel, Field


class SkillReferenceDocCreate(BaseModel):
    title: str = Field(default="", max_length=200, description="参考文档标题")
    content: str = Field(default="", description="参考文档内容")


class SkillReferenceDocUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200, description="参考文档标题")
    content: str | None = Field(default=None, description="参考文档内容")


class SkillReferenceDocResponse(BaseModel):
    id: str
    title: str
    content: str
    tokens: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
