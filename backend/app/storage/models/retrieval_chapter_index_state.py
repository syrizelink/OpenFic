# -*- coding: utf-8 -*-
"""Persistent per-chapter retrieval index state."""

from datetime import UTC, datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class RetrievalChapterIndexState(SQLModel, table=True):
    """Chapter-level retrieval indexing state for one project index."""

    __tablename__ = "retrieval_chapter_index_states"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "chapter_id",
            "index_key",
            name="uq_retrieval_chapter_index_state",
        ),
    )

    id: str = Field(default_factory=generate_id, primary_key=True)
    project_id: str = Field(index=True, foreign_key="projects.id")
    chapter_id: str = Field(index=True, foreign_key="chapters.id")
    index_key: str = Field(index=True, max_length=200)
    status: str = Field(default="not_indexed", max_length=30, index=True)
    source_hash: str | None = Field(default=None, max_length=128)
    embedding_model_ref_id: str | None = Field(
        default=None,
        foreign_key="models.id",
        index=True,
        max_length=200,
    )
    chunk_count: int | None = Field(default=None, ge=0)
    job_id: str | None = Field(default=None, foreign_key="background_jobs.id", index=True)
    item_id: str | None = Field(
        default=None,
        foreign_key="background_job_items.id",
        index=True,
    )
    indexed_at: datetime | None = Field(default=None, index=True)
    error_message: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
