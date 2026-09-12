# -*- coding: utf-8 -*-
"""Chapter Context API Schemas - Model permintaan/respons konteks bab."""

from datetime import datetime

from pydantic import BaseModel, Field


class ContextFieldResponse(BaseModel):
    """Respons satu field konteks (teks biasa)."""

    content: str = Field(description="Isi field")


class SummaryStatusResponse(BaseModel):
    """Respons status ringkasan bab."""

    chapter_id: str
    volume_id: str | None = None
    status: str
    is_stale: bool = False
    summary_id: str | None = None
    updated_at: datetime | None = None


class EnqueueSummaryRequest(BaseModel):
    """Permintaan penambahan tugas ringkasan secara manual."""

    summary_type: str = Field(default="chapter", description="chapter, long_term, atau all")
    chapter_id: str | None = Field(default=None, description="ID bab; bila kosong memakai bab saat ini")
    start_order: int | None = Field(default=None, description="order bab awal rentang")
    end_order: int | None = Field(default=None, description="order bab akhir rentang")
    model_id: str | None = Field(default=None, description="ID model opsional")


class EnqueueSummaryResponse(BaseModel):
    """Respons penambahan tugas ringkasan ke antrean."""

    summary_id: str | None = None
    status: str
    job_id: str | None = None
    item_count: int = 0


class MissingChapterSummaryItem(BaseModel):
    """Item ringkasan bab pada panel pemeliharaan ringkasan."""

    chapter_id: str
    chapter_order: int
    volume_id: str | None = None
    volume_title: str | None = None
    volume_order: int | None = None
    chapter_title: str
    word_count: int = 0
    status: str
    is_stale: bool = False
    summary_id: str | None = None
    progress_message: str | None = None


class SkippedChapterSummaryItem(BaseModel):
    """Item bab yang ringkasannya dilewati karena jumlah kata kurang."""

    chapter_id: str
    chapter_order: int
    volume_id: str | None = None
    volume_title: str | None = None
    volume_order: int | None = None
    chapter_title: str
    word_count: int


class MissingLongTermSummaryItem(BaseModel):
    """Item ringkasan rentang pada panel pemeliharaan ringkasan."""

    start_order: int
    end_order: int
    start_volume_title: str | None = None
    start_chapter_title: str = ""
    end_volume_title: str | None = None
    end_chapter_title: str = ""
    status: str
    is_stale: bool = False
    summary_id: str | None = None
    progress_message: str | None = None


class SummaryBatchProgressItem(BaseModel):
    """Progres agregat antrean batch ringkasan."""

    model_config = {"from_attributes": True}

    job_id: str
    status: str
    progress_current: int = 0
    progress_total: int | None = None
    progress_percent: int | None = None
    progress_message: str | None = None
    total_item_count: int = 0
    completed_item_count: int = 0
    running_item_count: int = 0
    queued_item_count: int = 0
    created_at: datetime
    updated_at: datetime


class SummaryMaintenanceResponse(BaseModel):
    """Status pemeliharaan ringkasan."""

    auto_generation_blocked: bool = False
    block_reason_code: str | None = None
    block_reason_params: dict[str, int | str] | None = None
    missing_or_failed_chapter_summaries: list[MissingChapterSummaryItem] = Field(default_factory=list)
    missing_or_failed_long_term_summaries: list[MissingLongTermSummaryItem] = Field(default_factory=list)
    skipped_chapter_summaries: list[SkippedChapterSummaryItem] = Field(default_factory=list)
    batch_progress: SummaryBatchProgressItem | None = None
    active_jobs: list["SummaryBackgroundJobItem"] = Field(default_factory=list)


class SummaryBackgroundJobItem(BaseModel):
    """Status tugas latar belakang terkait ringkasan."""

    model_config = {"from_attributes": True}

    job_id: str
    job_type: str
    status: str
    chapter_id: str | None = None
    summary_id: str | None = None
    start_order: int | None = None
    end_order: int | None = None
    progress_current: int = 0
    progress_total: int | None = None
    progress_message: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class SummaryPanelResponse(BaseModel):
    """Respons panel ringkasan."""

    maintenance: SummaryMaintenanceResponse


class SummaryRealtimeSnapshotSummaryResponse(BaseModel):
    """Payload summary pada snapshot ringkasan real-time."""

    statuses: list[SummaryStatusResponse] = Field(default_factory=list)
    maintenance: SummaryMaintenanceResponse


class SummaryRealtimeSnapshotResponse(BaseModel):
    """Respons snapshot real-time ringkasan bab."""

    project_id: str
    project_revision: int
    summary: SummaryRealtimeSnapshotSummaryResponse


class ChapterSummaryListItemResponse(BaseModel):
    """Item daftar panel ringkasan bab."""

    chapter_id: str
    chapter_order: int
    volume_id: str | None = None
    volume_title: str | None = None
    volume_order: int | None = None
    chapter_title: str
    status: str
    is_stale: bool = False
    summary_id: str | None = None
    start_time: str = ""
    end_time: str = ""
    characters: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    summary: str = ""
    error_message: str | None = None
    updated_at: datetime | None = None


class ChapterSummaryListResponse(BaseModel):
    """Respons daftar panel ringkasan bab."""

    items: list[ChapterSummaryListItemResponse] = Field(default_factory=list)
    total: int
    page: int
    page_size: int


class LongTermSummaryListItemResponse(BaseModel):
    """Item daftar panel ringkasan rentang."""

    start_order: int
    end_order: int
    start_volume_title: str | None = None
    start_chapter_title: str = ""
    end_volume_title: str | None = None
    end_chapter_title: str = ""
    status: str
    is_stale: bool = False
    summary_id: str | None = None
    start_time: str = ""
    end_time: str = ""
    summary: str = ""
    error_message: str | None = None
    updated_at: datetime | None = None


class LongTermSummaryListResponse(BaseModel):
    """Respons daftar panel ringkasan rentang."""

    items: list[LongTermSummaryListItemResponse] = Field(default_factory=list)
    total: int
    page: int
    page_size: int


class DeleteChapterSummariesRequest(BaseModel):
    """Permintaan penghapusan ringkasan bab."""

    chapter_ids: list[str] = Field(default_factory=list, description="Daftar ID bab yang ringkasannya akan dihapus")


class DeleteLongTermSummariesRequest(BaseModel):
    """Permintaan penghapusan ringkasan rentang."""

    ranges: list[tuple[int, int]] = Field(
        default_factory=list,
        description="Daftar rentang (start_order, end_order) yang akan dihapus; bila kosong semua dihapus",
    )


class ContextPartResponse(BaseModel):
    """Respons bagian konteks."""

    content: str = Field(description="Isi konteks")
    token_count: int = Field(description="Jumlah token")
    chapter_range: tuple[int, int] = Field(description="Rentang bab (start, end)")


class BuiltContextResponse(BaseModel):
    """Respons konteks yang sudah dibangun."""

    latest_field: ContextPartResponse = Field(description="Konteks bab terbaru")
    near_field: ContextPartResponse = Field(description="Konteks dekat")
    mid_field: ContextPartResponse = Field(description="Konteks menengah")
    far_field: ContextPartResponse = Field(description="Konteks jauh")
