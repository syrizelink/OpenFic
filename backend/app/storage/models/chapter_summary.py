# -*- coding: utf-8 -*-
"""Chapter summary persistence models."""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class ChapterSummary(SQLModel, table=True):
    """Structured chapter and long-term summary rows."""

    __tablename__ = "chapter_summaries"

    id: str = Field(default_factory=generate_id, primary_key=True)
    project_id: str = Field(index=True, foreign_key="projects.id")
    summary_type: str = Field(max_length=20, index=True, description="chapter 或 long_term")
    status: str = Field(default="not_generated", max_length=30, index=True)

    chapter_id: str | None = Field(default=None, index=True, foreign_key="chapters.id")
    volume_id: str | None = Field(default=None, index=True, foreign_key="volumes.id")
    chapter_order: int | None = Field(default=None, index=True)
    start_order: int | None = Field(default=None, index=True)
    end_order: int | None = Field(default=None, index=True)

    start_time: str = Field(default="")
    end_time: str = Field(default="")
    characters_json: str = Field(default="[]")
    locations_json: str = Field(default="[]")
    summary: str = Field(default="")
    token_count: int = Field(default=0, description="摘要 token 数")
    error_message: str | None = Field(default=None)
    source_content_normalized: str = Field(default="")
    source_chapter_ids_json: str = Field(default="[]")
    source_chapter_summary_signatures_json: str = Field(default="[]")
    model_id: str | None = Field(default=None, max_length=200)
    job_id: str | None = Field(default=None, index=True)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
