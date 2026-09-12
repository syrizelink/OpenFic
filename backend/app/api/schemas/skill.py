# -*- coding: utf-8 -*-
"""Skill API Schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.api.schemas.skill_reference_doc import SkillReferenceDocResponse


class SkillCreate(BaseModel):
    name: str = Field(default="", description="Nama skill")
    summary: str = Field(default="", description="Ringkasan skill")
    content: str = Field(default="", description="Isi skill")
    is_enabled: bool = Field(default=False, description="Apakah diaktifkan")


class SkillUpdate(BaseModel):
    name: str | None = Field(default=None, description="Nama skill")
    summary: str | None = Field(default=None, description="Ringkasan skill")
    content: str | None = Field(default=None, description="Isi skill")
    is_enabled: bool | None = Field(default=None, description="Apakah diaktifkan")


class SkillResponse(BaseModel):
    id: str
    name: str
    summary: str
    content: str
    is_enabled: bool
    is_complete: bool
    source: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SkillListResponse(BaseModel):
    items: list[SkillResponse]
    total: int
    page: int
    page_size: int


class SkillImportResponse(BaseModel):
    skill: SkillResponse
    reference_docs: list[SkillReferenceDocResponse]
    is_recognized: bool
