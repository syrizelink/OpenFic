# -*- coding: utf-8 -*-
"""Model data SkillReferenceDoc - dokumen referensi skill."""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class SkillReferenceDoc(SQLModel, table=True):
    """Dokumen referensi milik sebuah Skill."""

    __tablename__ = "skill_reference_docs"

    id: str = Field(default_factory=generate_id, primary_key=True)
    skill_db_id: str = Field(default="", foreign_key="skills.id", index=True)
    title: str = Field(default="", max_length=200)
    content: str = Field(default="")
    tokens: int = Field(default=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
