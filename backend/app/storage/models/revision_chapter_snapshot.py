# -*- coding: utf-8 -*-
"""Materialized chapter snapshot for a revision."""

from datetime import UTC, datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class RevisionChapterSnapshot(SQLModel, table=True):
    """Chapter state after a revision completes or reaches a visible checkpoint."""

    __tablename__ = "revision_chapter_snapshots"
    __table_args__ = (
        UniqueConstraint("revision_id", "chapter_id", name="uq_revision_chapter_snapshot"),
    )

    id: str = Field(default_factory=generate_id, primary_key=True)
    revision_id: str = Field(index=True, foreign_key="revisions.id")
    chapter_id: str = Field(index=True)
    project_id: str = Field(index=True, foreign_key="projects.id")
    exists: bool = Field(default=True)
    title: str | None = Field(default=None, max_length=200)
    content: str | None = Field(default=None)
    word_count: int | None = Field(default=None)
    chapter_order: int | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
