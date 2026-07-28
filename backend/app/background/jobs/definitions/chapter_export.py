"""章节 TXT 导出后台任务定义。"""

from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from app.background.jobs.base import JobDefinition
from app.background.jobs.constants import JOB_QUEUE_DEFAULT, JOB_TYPE_CHAPTER_EXPORT
from app.background.runtime.context import JobContext
from app.chapter_export import service as chapter_export_service


class ChapterExportChapterInput(BaseModel):
    id: str
    volume_id: str
    title: str
    word_count: int


class ChapterExportVolumeInput(BaseModel):
    id: str
    title: str
    order: int
    chapter_ids: list[str]


class ChapterExportInput(BaseModel):
    project_id: str
    filename: str
    mode: str
    chapters: list[ChapterExportChapterInput] = Field(min_length=1)
    volumes: list[ChapterExportVolumeInput]
    chapter_count: int
    word_count: int
    volume_count: int


class ChapterExportResult(BaseModel):
    filename: str
    volume_count: int
    chapter_count: int
    word_count: int
    expires_at: str


async def handle_chapter_export(context: JobContext) -> dict[str, Any]:
    """写入章节 TXT 成品。"""
    ChapterExportInput.model_validate(context.input)
    try:
        return await chapter_export_service.write_chapter_export(context)
    except (chapter_export_service.ChapterExportSelectionError, RuntimeError):
        raise
    except Exception as exc:
        logger.bind(job_id=context.job_id).opt(exception=True).error(
            f"chapter export failed: {exc}"
        )
        raise RuntimeError("导出文件生成失败，请重试") from exc


async def cleanup_chapter_export(_context: JobContext, _reason: str) -> None:
    """取消、失败或超时时删除任务文件。"""
    await chapter_export_service._delete_export_files(_context.job_id)


CHAPTER_EXPORT_JOB = JobDefinition(
    type=JOB_TYPE_CHAPTER_EXPORT,
    name="Chapter export",
    description="Export selected project chapters as a TXT file.",
    input_model=ChapterExportInput,
    result_model=ChapterExportResult,
    handler=handle_chapter_export,
    on_failed=cleanup_chapter_export,
    on_timeout=cleanup_chapter_export,
    on_cancelled=cleanup_chapter_export,
    default_queue=JOB_QUEUE_DEFAULT,
    default_timeout_seconds=3600,
    default_max_attempts=1,
    supports_cancel=True,
)
