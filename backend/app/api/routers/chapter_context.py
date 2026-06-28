# -*- coding: utf-8 -*-
"""Chapter Context Router - 章节上下文 API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.chapter_context import (
    BuiltContextResponse,
    ChapterSummaryListItemResponse,
    ChapterSummaryListResponse,
    ContextFieldResponse,
    ContextPartResponse,
    DeleteChapterSummariesRequest,
    DeleteLongTermSummariesRequest,
    EnqueueSummaryRequest,
    EnqueueSummaryResponse,
    LongTermSummaryListItemResponse,
    LongTermSummaryListResponse,
    MissingChapterSummaryItem,
    MissingLongTermSummaryItem,
    SkippedChapterSummaryItem,
    SummaryBatchProgressItem,
    SummaryRealtimeSnapshotResponse,
    SummaryRealtimeSnapshotSummaryResponse,
    SummaryPanelResponse,
    SummaryMaintenanceResponse,
    SummaryBackgroundJobItem,
    SummaryStatusResponse,
)
from app.background.jobs.states import JOB_STATUS_PENDING, JOB_STATUS_RUNNING
from app.background.jobs import service as background_job_service
from app.core.errors import NotFoundError, ValidationError
from app.memory.chapter import build_context
from app.memory.chapter.summary_service import (
    AUTO_GENERATION_BLOCK_CHAPTER_THRESHOLD,
    MIN_CHAPTER_SUMMARY_WORD_COUNT,
    SUMMARY_BATCH_ITEM_TYPE_CHAPTER,
    SUMMARY_BATCH_ITEM_TYPE_LONG_TERM,
    build_long_term_summary_window,
    enqueue_chapter_summary,
    enqueue_long_term_summary_range,
    append_chapter_summary_items,
    append_long_term_summary_items,
    is_chapter_summary_skipped,
    is_chapter_summary_stale,
    is_long_term_summary_stale,
    list_all_missing_summary_ranges,
    list_eligible_long_term_ranges,
    list_active_summary_jobs,
    list_chapter_summaries,
    list_long_term_summaries,
    parse_summary_list,
)
from app.storage.database import get_session
from app.storage.repos import chapter_repo, chapter_summary_repo, volume_repo


SUMMARY_ITEM_STAGE_TOTAL = 3


def _build_batch_progress(active_jobs: list, batch_job) -> SummaryBatchProgressItem | None:
    if batch_job is None:
        return None
    progress = background_job_service.parse_json_object(batch_job.progress_json)
    completed_item_count_raw = progress.get("completed_item_count")
    completed_item_count = completed_item_count_raw if isinstance(completed_item_count_raw, int) else 0
    batch_total_raw = progress.get("total_item_count")
    batch_total = batch_total_raw if isinstance(batch_total_raw, int) else 0
    running_item_count_raw = progress.get("running_item_count")
    persisted_running_item_count = running_item_count_raw if isinstance(running_item_count_raw, int) else None
    queued_item_count_raw = progress.get("queued_item_count")
    persisted_queued_item_count = queued_item_count_raw if isinstance(queued_item_count_raw, int) else None
    running_item_count = (
        persisted_running_item_count
        if persisted_running_item_count is not None
        else sum(1 for job in active_jobs if job.status == JOB_STATUS_RUNNING)
    )
    queued_item_count = (
        persisted_queued_item_count
        if persisted_queued_item_count is not None
        else sum(1 for job in active_jobs if job.status == JOB_STATUS_PENDING)
    )
    total_item_count = max(batch_total, completed_item_count + running_item_count + queued_item_count)
    progress_current_raw = progress.get("current")
    progress_current = progress_current_raw if isinstance(progress_current_raw, int) else 0
    progress_total_raw = progress.get("total")
    progress_total = progress_total_raw if isinstance(progress_total_raw, int) else None
    progress_percent_raw = progress.get("progress_percent")
    progress_percent = progress_percent_raw if isinstance(progress_percent_raw, int) else None
    if progress_total is None and total_item_count > 0:
        progress_total = total_item_count * SUMMARY_ITEM_STAGE_TOTAL
    if progress_percent is None and progress_total and progress_total > 0:
        progress_percent = min(100, round((progress_current / progress_total) * 100))
    progress_message = progress.get("message") if isinstance(progress.get("message"), str) else None
    return SummaryBatchProgressItem(
        job_id=batch_job.id,
        status=batch_job.status,
        progress_current=progress_current,
        progress_total=progress_total,
        progress_percent=progress_percent,
        progress_message=progress_message,
        total_item_count=total_item_count,
        completed_item_count=completed_item_count,
        running_item_count=running_item_count,
        queued_item_count=queued_item_count,
        created_at=batch_job.created_at,
        updated_at=batch_job.updated_at,
    )

router = APIRouter(tags=["chapter-context"])


def _chapter_summary_status(summary, chapter, *, active_job=None) -> str:
    if active_job is not None:
        return _maintenance_status_from_job(active_job.status)
    if summary is None:
        return "not_generated"
    return summary.status


def _maintenance_status_from_job(job_status: str) -> str:
    if job_status == JOB_STATUS_PENDING:
        return "queued"
    if job_status == JOB_STATUS_RUNNING:
        return "running"
    return job_status


def _volume_brief(volume):
    return {
        "volume_id": volume.id,
        "volume_title": volume.title,
        "volume_order": volume.order,
    }


def _long_term_summary_list_item(
    summary,
    start_order: int,
    end_order: int,
    *,
    is_stale: bool = False,
) -> LongTermSummaryListItemResponse:
    if summary is None:
        return LongTermSummaryListItemResponse(
            start_order=start_order,
            end_order=end_order,
            status="not_generated",
            is_stale=False,
            summary_id=None,
            updated_at=None,
        )
    return LongTermSummaryListItemResponse(
        start_order=start_order,
        end_order=end_order,
        status=summary.status,
        is_stale=is_stale,
        summary_id=summary.id,
        start_time=summary.start_time,
        end_time=summary.end_time,
        summary=summary.summary,
        error_message=summary.error_message,
        updated_at=summary.updated_at,
    )


async def _build_maintenance_response(
    session: AsyncSession, project_id: str
) -> SummaryMaintenanceResponse:
    chapters = await chapter_repo.list_by_project(session, project_id)
    volumes = await volume_repo.list_by_project(session, project_id)
    chapter_summaries = await list_chapter_summaries(session, project_id)
    long_term_summaries = await list_long_term_summaries(session, project_id)
    summary_by_chapter_id = {summary.chapter_id: summary for summary in chapter_summaries}
    active_jobs = await list_active_summary_jobs(
        session,
        project_id,
        chapter_summaries,
        long_term_summaries,
    )
    batch_jobs = await background_job_service.list_jobs(
        session,
        subject_type="project",
        subject_id=project_id,
        statuses={JOB_STATUS_PENDING, JOB_STATUS_RUNNING},
        job_types={"summary_batch"},
        limit=1,
        offset=0,
    )
    batch_job = batch_jobs[0] if batch_jobs else None
    if batch_job is None and active_jobs:
        recent_batch_jobs = await background_job_service.list_jobs(
            session,
            subject_type="project",
            subject_id=project_id,
            job_types={"summary_batch"},
            limit=1,
            offset=0,
        )
        batch_job = recent_batch_jobs[0] if recent_batch_jobs else None
    active_chapter_job_by_id = {
        job.chapter_id: job
        for job in active_jobs
        if job.job_type == SUMMARY_BATCH_ITEM_TYPE_CHAPTER and job.chapter_id is not None
    }
    volumes_by_id = {volume.id: volume for volume in volumes}
    missing_chapters: list[MissingChapterSummaryItem] = []
    skipped_chapters: list[SkippedChapterSummaryItem] = []
    for chapter in chapters:
        volume = volumes_by_id.get(chapter.volume_id) if chapter.volume_id else None
        if is_chapter_summary_skipped(chapter):
            skipped_chapters.append(
                SkippedChapterSummaryItem(
                    chapter_id=chapter.id,
                    chapter_order=chapter.order,
                    chapter_title=chapter.title,
                    word_count=chapter.word_count,
                    **(_volume_brief(volume) if volume is not None else {}),
                )
            )
            continue
        summary = summary_by_chapter_id.get(chapter.id)
        status = _chapter_summary_status(summary, chapter)
        active_job = active_chapter_job_by_id.get(chapter.id)
        if active_job is not None:
            status = _maintenance_status_from_job(active_job.status)
        if status == "ready":
            continue
        missing_chapters.append(
            MissingChapterSummaryItem(
                chapter_id=chapter.id,
                chapter_order=chapter.order,
                chapter_title=chapter.title,
                status=status,
                is_stale=is_chapter_summary_stale(summary, chapter),
                summary_id=summary.id if summary else None,
                progress_message=active_job.progress_message if active_job else None,
                **(_volume_brief(volume) if volume is not None else {}),
            )
        )

    long_term_by_range = {
        (summary.start_order, summary.end_order): summary for summary in long_term_summaries
    }
    active_long_term_job_by_range = {
        (job.start_order, job.end_order): job
        for job in active_jobs
        if job.job_type == SUMMARY_BATCH_ITEM_TYPE_LONG_TERM
        and job.start_order is not None
        and job.end_order is not None
    }
    missing_long_terms: list[MissingLongTermSummaryItem] = []
    for start_order, end_order in list_eligible_long_term_ranges(chapters, volumes, chapter_summaries):
        existing = long_term_by_range.get((start_order, end_order))
        status = existing.status if existing else "not_generated"
        is_stale = is_long_term_summary_stale(existing, chapters, chapter_summaries, volumes)
        active_job = active_long_term_job_by_range.get((start_order, end_order))
        if active_job is not None:
            status = _maintenance_status_from_job(active_job.status)
            is_stale = False
        if status not in {"not_generated", "failed", "queued", "running"} and not is_stale:
            continue
        missing_long_terms.append(
            MissingLongTermSummaryItem(
                start_order=start_order,
                end_order=end_order,
                status=status,
                is_stale=is_stale,
                summary_id=existing.id if existing else None,
                progress_message=active_job.progress_message if active_job else None,
            )
        )

    has_ready_chapter_summary = any(
        summary.status == "ready" for summary in chapter_summaries
    )
    eligible_chapter_count = sum(
        1 for chapter in chapters if not is_chapter_summary_skipped(chapter)
    )
    auto_blocked = (
        eligible_chapter_count > AUTO_GENERATION_BLOCK_CHAPTER_THRESHOLD
        and not has_ready_chapter_summary
    )
    return SummaryMaintenanceResponse(
        auto_generation_blocked=auto_blocked,
        block_reason=(
            f"可参与摘要的章节过多（至少 {MIN_CHAPTER_SUMMARY_WORD_COUNT} 字），需要在面板中手动生成或启用摘要。"
        )
        if auto_blocked
        else None,
        missing_or_failed_chapter_summaries=missing_chapters,
        missing_or_failed_long_term_summaries=missing_long_terms,
        skipped_chapter_summaries=skipped_chapters,
        batch_progress=_build_batch_progress(active_jobs, batch_job),
        active_jobs=[SummaryBackgroundJobItem.model_validate(job, from_attributes=True) for job in active_jobs],
    )


async def build_summary_statuses_response(
    session: AsyncSession,
    project_id: str,
) -> list[SummaryStatusResponse]:
    chapters = await chapter_repo.list_by_project(session, project_id)
    summaries = await list_chapter_summaries(session, project_id)
    summary_by_chapter_id = {summary.chapter_id: summary for summary in summaries}
    active_jobs = await list_active_summary_jobs(session, project_id, summaries, [])
    active_chapter_job_by_id = {
        job.chapter_id: job
        for job in active_jobs
        if job.job_type == SUMMARY_BATCH_ITEM_TYPE_CHAPTER and job.chapter_id is not None
    }
    return [
        SummaryStatusResponse(
            chapter_id=chapter.id,
            volume_id=chapter.volume_id,
            status=_chapter_summary_status(
                summary,
                chapter,
                active_job=active_chapter_job_by_id.get(chapter.id),
            ),
            is_stale=is_chapter_summary_stale(summary, chapter),
            summary_id=summary.id if summary else None,
            updated_at=summary.updated_at if summary else None,
        )
        for chapter in chapters
        for summary in [summary_by_chapter_id.get(chapter.id)]
    ]


async def build_summary_panel_response(
    session: AsyncSession,
    project_id: str,
) -> SummaryPanelResponse:
    return SummaryPanelResponse(
        maintenance=await _build_maintenance_response(session, project_id),
    )


async def build_summary_realtime_snapshot(
    session: AsyncSession,
    project_id: str,
    project_revision: int,
) -> SummaryRealtimeSnapshotResponse:
    statuses = await build_summary_statuses_response(session, project_id)
    maintenance = await _build_maintenance_response(session, project_id)
    return SummaryRealtimeSnapshotResponse(
        project_id=project_id,
        project_revision=project_revision,
        summary=SummaryRealtimeSnapshotSummaryResponse(
            statuses=statuses,
            maintenance=maintenance,
        ),
    )


@router.get(
    "/projects/{project_id}/chapter-context/summaries/chapters",
    response_model=ChapterSummaryListResponse,
    summary="获取章节摘要面板列表",
)
async def list_chapter_summary_items(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    volume_id: str | None = Query(default=None, description="按卷过滤"),
) -> ChapterSummaryListResponse:
    offset = (page - 1) * page_size
    total = await chapter_summary_repo.count_chapter_summaries_by_project(
        session, project_id, volume_id=volume_id
    )
    summaries = await chapter_summary_repo.list_chapter_summaries_by_project_page(
        session, project_id, offset=offset, limit=page_size, volume_id=volume_id
    )
    chapters = await chapter_repo.list_by_project(session, project_id)
    chapter_by_id = {chapter.id: chapter for chapter in chapters}
    volumes = await volume_repo.list_by_project(session, project_id)
    volumes_by_id = {volume.id: volume for volume in volumes}
    active_jobs = await list_active_summary_jobs(session, project_id, summaries, [])
    active_chapter_job_by_id = {
        job.chapter_id: job
        for job in active_jobs
        if job.job_type == SUMMARY_BATCH_ITEM_TYPE_CHAPTER and job.chapter_id is not None
    }
    items: list[ChapterSummaryListItemResponse] = []
    for summary in summaries:
        chapter_id = summary.chapter_id
        chapter = chapter_by_id.get(chapter_id) if chapter_id is not None else None
        active_job = (
            active_chapter_job_by_id.get(chapter_id) if chapter_id is not None else None
        )
        resolved_volume_id = summary.volume_id or (chapter.volume_id if chapter is not None else None)
        volume = volumes_by_id.get(resolved_volume_id) if resolved_volume_id else None
        items.append(
            ChapterSummaryListItemResponse(
                chapter_id=chapter_id or "",
                chapter_order=chapter.order if chapter is not None else summary.chapter_order or 0,
                chapter_title=chapter.title if chapter is not None else "未命名章节",
                status=_chapter_summary_status(
                    summary,
                    chapter,
                    active_job=active_job,
                ),
                is_stale=is_chapter_summary_stale(summary, chapter)
                if chapter is not None
                else False,
                summary_id=summary.id,
                start_time=summary.start_time,
                end_time=summary.end_time,
                characters=parse_summary_list(summary.characters_json),
                locations=parse_summary_list(summary.locations_json),
                summary=summary.summary,
                error_message=summary.error_message,
                updated_at=summary.updated_at,
                **(_volume_brief(volume) if volume is not None else {}),
            )
        )
    return ChapterSummaryListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.delete(
    "/projects/{project_id}/chapter-context/summaries/chapters",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="批量删除章节摘要",
)
async def delete_chapter_summaries(
    project_id: str,
    data: DeleteChapterSummariesRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    chapters = await chapter_repo.list_by_project(session, project_id)
    chapter_ids = {chapter.id for chapter in chapters}
    invalid_ids = [chapter_id for chapter_id in data.chapter_ids if chapter_id not in chapter_ids]
    if invalid_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"章节不存在: {invalid_ids[0]}",
        )
    if not data.chapter_ids:
        await chapter_summary_repo.delete_all_chapter_summaries_by_project(session, project_id)
    else:
        await chapter_summary_repo.delete_by_chapter_ids(session, data.chapter_ids)
    await session.commit()


@router.delete(
    "/projects/{project_id}/chapter-context/summaries/long-term",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="批量删除区间摘要",
)
async def delete_long_term_summaries(
    project_id: str,
    data: DeleteLongTermSummariesRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    if not data.ranges:
        await chapter_summary_repo.delete_all_long_term_summaries_by_project(session, project_id)
    else:
        await chapter_summary_repo.delete_long_term_summaries_by_ranges(
            session, project_id, data.ranges
        )
    await session.commit()


@router.get(
    "/projects/{project_id}/chapter-context/summaries/long-term",
    response_model=LongTermSummaryListResponse,
    summary="分页获取区间摘要",
)
async def list_long_terms_page(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> LongTermSummaryListResponse:
    chapters = await chapter_repo.list_by_project(session, project_id)
    volumes = await volume_repo.list_by_project(session, project_id)
    chapter_summaries = await list_chapter_summaries(session, project_id)
    summaries = await list_long_term_summaries(session, project_id)
    summaries.sort(key=lambda item: (item.start_order or 0, item.end_order or 0, item.updated_at))
    total = len(summaries)
    offset = (page - 1) * page_size
    page_summaries = summaries[offset : offset + page_size]
    items = [
        _long_term_summary_list_item(
            summary,
            summary.start_order or 0,
            summary.end_order or 0,
            is_stale=is_long_term_summary_stale(
                summary,
                chapters,
                chapter_summaries,
                volumes,
            ),
        )
        for summary in page_summaries
    ]
    return LongTermSummaryListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/projects/{project_id}/chapter-context/summaries/enqueue",
    response_model=EnqueueSummaryResponse,
    summary="加入章节摘要生成队列",
)
async def enqueue_summary(
    project_id: str,
    data: EnqueueSummaryRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EnqueueSummaryResponse:
    try:
        if data.summary_type == "chapter":
            if not data.chapter_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="缺少 chapter_id",
                )
            chapter = await chapter_repo.get_by_id(session, data.chapter_id)
            if chapter is None or chapter.project_id != project_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"章节不存在: {data.chapter_id}",
                )
            summary = await enqueue_chapter_summary(
                session, data.chapter_id, model_id=data.model_id
            )
            item_count = 1
        elif data.summary_type == "long_term":
            if data.start_order is None or data.end_order is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="缺少 start_order 或 end_order",
                )
            chapters = await chapter_repo.list_by_project(session, project_id)
            volumes = await volume_repo.list_by_project(session, project_id)
            chapter_summaries = await list_chapter_summaries(session, project_id)
            window = build_long_term_summary_window(
                chapters,
                volumes,
                chapter_summaries,
                data.start_order,
                data.end_order,
            )
            if window is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="该区间缺少可参与聚合的章节摘要，需先生成满足条件的章节摘要。",
                )
            summary = await enqueue_long_term_summary_range(
                session,
                project_id,
                data.start_order,
                data.end_order,
                window.source_summaries,
                model_id=data.model_id,
            )
            item_count = 1
        elif data.summary_type == "all":
            chapter_ids, ranges = await list_all_missing_summary_ranges(session, project_id)
            chapter_result = None
            long_term_result = None
            if chapter_ids:
                chapter_result = await append_chapter_summary_items(
                    session,
                    project_id,
                    chapter_ids,
                    model_id=data.model_id,
                )
            if ranges:
                long_term_result = await append_long_term_summary_items(
                    session,
                    project_id,
                    ranges,
                    model_id=data.model_id,
                )
            item_count = (len(chapter_result.item_ids) if chapter_result else 0) + (
                len(long_term_result.item_ids) if long_term_result else 0
            )
            batch_job_id = (
                chapter_result.batch_job_id if chapter_result is not None else long_term_result.batch_job_id if long_term_result is not None else None
            )
            await background_job_service.commit_and_notify(session)
            return EnqueueSummaryResponse(
                summary_id=None,
                status="queued" if item_count else "idle",
                job_id=batch_job_id,
                item_count=item_count,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="summary_type 必须是 chapter、long_term 或 all",
            )
        await background_job_service.commit_and_notify(session)
        return EnqueueSummaryResponse(
            summary_id=summary.id,
            status=summary.status,
            job_id=summary.job_id,
            item_count=item_count,
        )
    except NotFoundError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValidationError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/projects/{project_id}/chapter-context/context",
    response_model=BuiltContextResponse,
    summary="获取构建的上下文",
)
async def get_context(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    chapter_id: str = Query(description="当前章节 ID"),
) -> BuiltContextResponse:
    """获取构建的分层上下文。"""
    try:
        context = await build_context(session, project_id, chapter_id)
        return BuiltContextResponse(
            latest_field=ContextPartResponse(
                content=context.latest_field.content,
                token_count=context.latest_field.token_count,
                chapter_range=context.latest_field.chapter_range,
            ),
            near_field=ContextPartResponse(
                content=context.near_field.content,
                token_count=context.near_field.token_count,
                chapter_range=context.near_field.chapter_range,
            ),
            mid_field=ContextPartResponse(
                content=context.mid_field.content,
                token_count=context.mid_field.token_count,
                chapter_range=context.mid_field.chapter_range,
            ),
            far_field=ContextPartResponse(
                content=context.far_field.content,
                token_count=context.far_field.token_count,
                chapter_range=context.far_field.chapter_range,
            ),
        )
    except Exception as e:
        logger.error(f"构建上下文失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"构建失败: {str(e)}",
        )


@router.get(
    "/projects/{project_id}/chapter-context/near",
    response_model=ContextFieldResponse,
    summary="获取近场上下文",
)
async def get_near_field(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    chapter_id: str = Query(description="当前章节 ID"),
) -> ContextFieldResponse:
    try:
        context = await build_context(session, project_id, chapter_id)
        return ContextFieldResponse(content=context.near_field.content)
    except Exception as e:
        logger.error(f"获取近场上下文失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.get(
    "/projects/{project_id}/chapter-context/middle",
    response_model=ContextFieldResponse,
    summary="获取中场上下文",
)
async def get_middle_field(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    chapter_id: str = Query(description="当前章节 ID"),
) -> ContextFieldResponse:
    try:
        context = await build_context(session, project_id, chapter_id)
        return ContextFieldResponse(content=context.mid_field.content)
    except Exception as e:
        logger.error(f"获取中场上下文失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.get(
    "/projects/{project_id}/chapter-context/far",
    response_model=ContextFieldResponse,
    summary="获取远场上下文",
)
async def get_far_field(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    chapter_id: str = Query(description="当前章节 ID"),
) -> ContextFieldResponse:
    try:
        context = await build_context(session, project_id, chapter_id)
        return ContextFieldResponse(content=context.far_field.content)
    except Exception as e:
        logger.error(f"获取远场上下文失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")


@router.get(
    "/projects/{project_id}/chapter-context/latest",
    response_model=ContextFieldResponse,
    summary="获取最新章节内容",
)
async def get_latest_field(
    project_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    chapter_id: str = Query(description="当前章节 ID"),
) -> ContextFieldResponse:
    try:
        context = await build_context(session, project_id, chapter_id)
        if not context.latest_field.content:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"章节不存在: chapter_id={chapter_id}",
            )
        return ContextFieldResponse(content=context.latest_field.content)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取最新章节内容失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取失败: {str(e)}")
