# -*- coding: utf-8 -*-
"""Schemas for project retrieval index APIs."""

from pydantic import BaseModel, Field

IndexStatus = str
IndexMode = str


class IndexProjectStatusResponse(BaseModel):
    """Ringkasan status indeks satu proyek (tanpa ID internal)."""

    project_id: str
    enabled: bool
    status: IndexStatus
    title: str = ""
    total_chapters: int = 0
    indexed_count: int = 0
    pending_count: int = 0
    in_progress_count: int = 0
    failed_count: int = 0
    empty_content_count: int = 0
    last_error: str | None = None
    progress: float = 0.0


class IndexOverallStatusResponse(BaseModel):
    """Status indeks keseluruhan (diagregasi lintas proyek yang aktif)."""

    mode: IndexMode
    embedding_model_configured: bool
    total_projects: int = 0
    total_chapters: int = 0
    indexed_count: int = 0
    pending_count: int = 0
    in_progress_count: int = 0
    failed_count: int = 0
    projects: list[IndexProjectStatusResponse] = Field(default_factory=list)


class IndexStartResponse(BaseModel):
    """Respons pengindeksan yang dimulai manual."""

    project_id: str
    enqueued_count: int
    skipped_count: int = 0


class IndexStopResponse(BaseModel):
    """Respons pengindeksan yang dihentikan manual."""

    project_id: str
    stopped_count: int
