# -*- coding: utf-8 -*-
"""Materialized character snapshots for a revision."""

from datetime import UTC, datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class RevisionCharacterSnapshot(SQLModel, table=True):
    """Character state before a revision's change, used for rollback."""

    __tablename__ = "revision_character_snapshots"
    __table_args__ = (
        UniqueConstraint("revision_id", "character_id", name="uq_revision_character_snapshot"),
    )

    id: str = Field(default_factory=generate_id, primary_key=True)
    revision_id: str = Field(index=True, foreign_key="revisions.id")
    character_id: str = Field(index=True)
    project_id: str = Field(index=True, foreign_key="projects.id")
    exists: bool = Field(default=True)
    name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None)
    is_favorited: bool | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
