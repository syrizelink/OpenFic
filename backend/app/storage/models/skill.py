# -*- coding: utf-8 -*-
"""Model data Skill."""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class Skill(SQLModel, table=True):
    """Skill yang dapat disunting pengguna."""

    __tablename__ = "skills"

    id: str = Field(default_factory=generate_id, primary_key=True)
    name: str = Field(default="", max_length=200)
    summary: str = Field(default="")
    content: str = Field(default="")
    is_enabled: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def source(self) -> str:
        return "custom"
