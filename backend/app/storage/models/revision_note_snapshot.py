# -*- coding: utf-8 -*-
"""Materialized note and note-category snapshots for a revision."""

from datetime import UTC, datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class RevisionNoteSnapshot(SQLModel, table=True):
    """Note state before a revision's change, used for rollback."""

    __tablename__ = "revision_note_snapshots"
    __table_args__ = (
        UniqueConstraint("revision_id", "note_id", name="uq_revision_note_snapshot"),
    )

    id: str = Field(default_factory=generate_id, primary_key=True)
    revision_id: str = Field(index=True, foreign_key="revisions.id")
    note_id: str = Field(index=True)
    project_id: str = Field(index=True, foreign_key="projects.id")
    exists: bool = Field(default=True)
    category_id: str | None = Field(default=None, index=True)
    title: str | None = Field(default=None, max_length=200)
    content: str | None = Field(default=None)
    is_locked: bool | None = Field(default=None)
    is_hidden: bool | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RevisionNoteCategorySnapshot(SQLModel, table=True):
    """Note-category state before a revision's change, used for rollback."""

    __tablename__ = "revision_note_category_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "revision_id", "category_id", name="uq_revision_note_category_snapshot"
        ),
    )

    id: str = Field(default_factory=generate_id, primary_key=True)
    revision_id: str = Field(index=True, foreign_key="revisions.id")
    category_id: str = Field(index=True)
    project_id: str = Field(index=True, foreign_key="projects.id")
    exists: bool = Field(default=True)
    parent_id: str | None = Field(default=None, index=True)
    title: str | None = Field(default=None, max_length=200)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
