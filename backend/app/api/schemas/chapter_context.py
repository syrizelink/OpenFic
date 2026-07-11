# -*- coding: utf-8 -*-
"""Chapter Context API Schemas - 章节上下文请求/响应模型。"""

from datetime import datetime

from pydantic import BaseModel, Field


class ContextFieldResponse(BaseModel):
    """单个上下文字段响应（纯文本）。"""

    content: str = Field(description="字段内容")


class SummaryStatusResponse(BaseModel):
    """章节摘要状态响应。"""

    chapter_id: str
    volume_id: str | None = None
    status: str
    is_stale: bool = False
    summary_id: str | None = None
    updated_at: datetime | None = None


class EnqueueSummaryRequest(BaseModel):
    """手动加入摘要任务请求。"""

    summary_type: str = Field(default="chapter", description="chapter、long_term 或 all")
    chapter_id: str | None = Field(default=None, description="章节 ID；为空则使用当前章节")
    start_order: int | None = Field(default=None, description="区间起始章节 order")
    end_order: int | None = Field(default=None, description="区间结束章节 order")
    model_id: str | None = Field(default=None, description="可选模型 ID")


class EnqueueSummaryResponse(BaseModel):
    """摘要任务加入队列响应。"""

    summary_id: str | None = None
    status: str
    job_id: str | None = None
    item_count: int = 0


class MissingChapterSummaryItem(BaseModel):
    """摘要维护面板中的章节摘要项。"""

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
    """因字数不足而跳过摘要的章节项。"""

    chapter_id: str
    chapter_order: int
    volume_id: str | None = None
    volume_title: str | None = None
    volume_order: int | None = None
    chapter_title: str
    word_count: int


class MissingLongTermSummaryItem(BaseModel):
    """摘要维护面板中的区间摘要项。"""

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
    """摘要批处理队列的聚合进度。"""

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
    """摘要维护状态。"""

    auto_generation_blocked: bool = False
    block_reason_code: str | None = None
    block_reason_params: dict[str, int | str] | None = None
    missing_or_failed_chapter_summaries: list[MissingChapterSummaryItem] = Field(default_factory=list)
    missing_or_failed_long_term_summaries: list[MissingLongTermSummaryItem] = Field(default_factory=list)
    skipped_chapter_summaries: list[SkippedChapterSummaryItem] = Field(default_factory=list)
    batch_progress: SummaryBatchProgressItem | None = None
    active_jobs: list["SummaryBackgroundJobItem"] = Field(default_factory=list)


class SummaryBackgroundJobItem(BaseModel):
    """摘要相关后台任务状态。"""

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
    """摘要面板响应。"""

    maintenance: SummaryMaintenanceResponse


class SummaryRealtimeSnapshotSummaryResponse(BaseModel):
    """摘要实时快照中的 summary payload。"""

    statuses: list[SummaryStatusResponse] = Field(default_factory=list)
    maintenance: SummaryMaintenanceResponse


class SummaryRealtimeSnapshotResponse(BaseModel):
    """章节摘要实时快照响应。"""

    project_id: str
    project_revision: int
    summary: SummaryRealtimeSnapshotSummaryResponse


class ChapterSummaryListItemResponse(BaseModel):
    """章节摘要面板列表项。"""

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
    """章节摘要面板列表响应。"""

    items: list[ChapterSummaryListItemResponse] = Field(default_factory=list)
    total: int
    page: int
    page_size: int


class LongTermSummaryListItemResponse(BaseModel):
    """区间摘要面板列表项。"""

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
    """区间摘要面板列表响应。"""

    items: list[LongTermSummaryListItemResponse] = Field(default_factory=list)
    total: int
    page: int
    page_size: int


class DeleteChapterSummariesRequest(BaseModel):
    """删除章节摘要请求。"""

    chapter_ids: list[str] = Field(default_factory=list, description="要删除摘要的章节 ID 列表")


class DeleteLongTermSummariesRequest(BaseModel):
    """删除区间摘要请求。"""

    ranges: list[tuple[int, int]] = Field(
        default_factory=list,
        description="要删除的区间 (start_order, end_order) 列表，为空则删除全部",
    )


class ContextPartResponse(BaseModel):
    """上下文部分响应。"""

    content: str = Field(description="上下文内容")
    token_count: int = Field(description="token 数量")
    chapter_range: tuple[int, int] = Field(description="章节范围 (start, end)")


class BuiltContextResponse(BaseModel):
    """构建的上下文响应。"""

    latest_field: ContextPartResponse = Field(description="最新章节上下文")
    near_field: ContextPartResponse = Field(description="近场上下文")
    mid_field: ContextPartResponse = Field(description="中场上下文")
    far_field: ContextPartResponse = Field(description="远场上下文")
