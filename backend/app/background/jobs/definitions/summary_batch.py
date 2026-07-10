"""Unified summary batch background job definition."""

import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from app.background.jobs import service as job_service
from app.background.jobs import repos as job_repo
from app.background.jobs.base import JobDefinition
from app.background.jobs.constants import JOB_QUEUE_LLM, JOB_TYPE_SUMMARY_BATCH
from app.background.jobs.models import BackgroundJobItem
from app.background.jobs.states import JOB_STATUS_FAILED, JOB_STATUS_PENDING, JOB_STATUS_RUNNING, JOB_STATUS_SKIPPED, JOB_STATUS_SUCCEEDED
from app.background.llm.resolver import BackgroundModelUnavailableError, resolve_background_llm
from app.background.runtime.context import JobContext
from app.memory.chapter import summary_generator, summary_service
from app.storage.repos import chapter_repo


SUMMARY_ITEM_STAGE_TOTAL = 3


class SummaryBatchInput(BaseModel):
    project_id: str


class SummaryBatchContext(BaseModel):
    project_id: str
    model_policy: str = "light_model"
    model_id: str | None = None


async def _save_item(session, item: BackgroundJobItem) -> BackgroundJobItem:
    item.updated_at = datetime.now(UTC)
    return await job_repo.save_item(session, item)


async def _mark_item_running(session, item: BackgroundJobItem) -> BackgroundJobItem:
    item.status = JOB_STATUS_RUNNING
    item.started_at = item.started_at or datetime.now(UTC)
    item.finished_at = None
    return await _save_item(session, item)


async def _mark_item_terminal(session, item: BackgroundJobItem, status: str, *, error_message: str | None = None) -> BackgroundJobItem:
    item.status = status
    item.finished_at = datetime.now(UTC)
    item.error_json = None if error_message is None else json.dumps({"message": error_message}, ensure_ascii=False)
    return await _save_item(session, item)


async def _update_item_progress(session, item: BackgroundJobItem, *, current: int, total: int | None = None, message: str | None = None) -> BackgroundJobItem:
    return await job_service.update_item_progress(
        session,
        item,
        progress={"current": current, "total": total, "message": message},
    )


def _item_progress_message(item: BackgroundJobItem) -> str | None:
    progress = job_service.parse_json_object(item.progress_json)
    message = progress.get("message")
    return message if isinstance(message, str) else None


async def _publish_item_progress(
    context: JobContext,
    item: BackgroundJobItem,
    summary_row,
    *,
    current: int,
    total: int | None,
    message: str | None,
) -> None:
    await summary_service.publish_summary_batch_item_event(
        context.session,
        context.job,
        event_type="background_item_progress",
        item_id=item.id,
        item_type=item.type,
        payload=summary_service.build_summary_batch_item_event_payload(
            project_id=summary_row.project_id,
            status=JOB_STATUS_RUNNING,
            summary_id=summary_row.id,
            chapter_id=summary_row.chapter_id,
            start_order=summary_row.start_order,
            end_order=summary_row.end_order,
            is_stale=False,
            progress_current=current,
            progress_total=total,
            progress_message=message,
            error_message=None,
        ),
        publisher=context.publisher,
    )


async def _publish_item_terminal(
    context: JobContext,
    item: BackgroundJobItem,
    summary_row,
    *,
    terminal_status: str,
    error_message: str | None = None,
) -> None:
    await summary_service.publish_summary_batch_item_event(
        context.session,
        context.job,
        event_type=f"background_item_{terminal_status}",
        item_id=item.id,
        item_type=item.type,
        payload=summary_service.build_summary_batch_item_event_payload(
            project_id=summary_row.project_id,
            status=terminal_status,
            summary_id=summary_row.id,
            chapter_id=summary_row.chapter_id,
            start_order=summary_row.start_order,
            end_order=summary_row.end_order,
            is_stale=False,
            progress_current=SUMMARY_ITEM_STAGE_TOTAL,
            progress_total=SUMMARY_ITEM_STAGE_TOTAL,
            progress_message=_item_progress_message(item),
            error_message=error_message,
        ),
        publisher=context.publisher,
    )


def _item_progress_units(item: BackgroundJobItem) -> int:
    if item.status == JOB_STATUS_PENDING:
        return 0
    if item.status == JOB_STATUS_RUNNING:
        progress = job_service.parse_json_object(item.progress_json)
        current = int(progress.get("current") or 0)
        total = progress.get("total") if isinstance(progress.get("total"), int) else None
        if total is None or total <= 0:
            return max(current, 0)
        return max(0, min(current, total))
    return SUMMARY_ITEM_STAGE_TOTAL


def _build_batch_progress_payload(job, items: list[BackgroundJobItem], message: str | None) -> dict[str, Any]:
    completed_item_count = sum(
        1 for item in items if item.status in {JOB_STATUS_SUCCEEDED, JOB_STATUS_FAILED, JOB_STATUS_SKIPPED}
    )
    running_item_count = sum(1 for item in items if item.status == JOB_STATUS_RUNNING)
    queued_item_count = sum(1 for item in items if item.status == JOB_STATUS_PENDING)
    total_item_count = len(items)
    progress_total = total_item_count * SUMMARY_ITEM_STAGE_TOTAL if total_item_count > 0 else 0
    progress_current = min(sum(_item_progress_units(item) for item in items), progress_total)
    progress_percent = None
    if progress_total > 0:
        progress_percent = min(100, round((progress_current / progress_total) * 100))
    return {
        "current": progress_current,
        "total": progress_total,
        "message": message,
        "progress_percent": progress_percent,
        "total_item_count": total_item_count,
        "completed_item_count": completed_item_count,
        "running_item_count": running_item_count,
        "queued_item_count": queued_item_count,
        "job_id": job.id,
        "status": job.status,
    }


async def _update_batch_progress(session, context: JobContext, *, message: str | None = None) -> None:
    items = await job_service.list_job_items(session, job_id=context.job_id)
    progress_payload = _build_batch_progress_payload(context.job, items, message)
    await job_service.update_progress(
        session,
        context.publisher,
        context.job,
        current=int(progress_payload["current"]),
        total=int(progress_payload["total"]),
        message=message,
        extra_payload=progress_payload,
    )


async def _process_chapter_item(context: JobContext, item: BackgroundJobItem, metadata: SummaryBatchContext) -> None:
    payload = job_service.parse_json_object(item.payload_json)
    chapter_id = payload.get("chapter_id")
    if not isinstance(chapter_id, str):
        raise ValueError("缺少 chapter_id")

    try:
        resolved = await resolve_background_llm(
            context.session,
            model_policy=str(payload.get("model_policy") or metadata.model_policy),
            model_id=str(payload.get("model_id")) if isinstance(payload.get("model_id"), str) else metadata.model_id,
        )
    except BackgroundModelUnavailableError as exc:
        summary = await summary_service.get_chapter_summary(context.session, chapter_id)
        if summary is not None:
            await summary_service.mark_summary_failed(context.session, summary, str(exc))
            await summary_service.publish_chapter_summary_update(context, summary)
        await _mark_item_terminal(context.session, item, JOB_STATUS_SKIPPED, error_message=str(exc))
        if summary is not None:
            await _publish_item_terminal(
                context,
                item,
                summary,
                terminal_status="skipped",
                error_message=str(exc),
            )
        return

    row = await summary_service.mark_chapter_summary_running(
        context.session,
        chapter_id,
        item.id,
        resolved.model.id,
    )
    await summary_service.publish_chapter_summary_update(context, row)
    await _update_item_progress(context.session, item, current=1, total=3, message="正在生成章节摘要")
    await _publish_item_progress(
        context,
        item,
        row,
        current=1,
        total=3,
        message="正在生成章节摘要",
    )
    await _update_batch_progress(context.session, context, message="正在生成章节摘要")
    await job_service.commit_and_notify(context.session)
    prompt = await summary_generator.build_chapter_summary_prompt(context.session, chapter_id)
    result = await summary_generator.generate_chapter_summary_from_prompt(resolved.client, prompt)
    row = await summary_service.save_chapter_summary_result(
        context.session,
        chapter_id,
        start_time=result.start_time,
        end_time=result.end_time,
        characters=result.characters,
        locations=result.locations,
        summary=result.summary,
        token_count=result.token_count,
        model_id=resolved.model.id,
        job_id=item.id,
    )
    await _update_item_progress(context.session, item, current=2, total=3, message="章节摘要已保存")
    await _publish_item_progress(
        context,
        item,
        row,
        current=2,
        total=3,
        message="章节摘要已保存",
    )
    await summary_service.publish_chapter_summary_update(context, row)
    await summary_service.enqueue_long_term_summary_if_ready(
        context.session,
        row.project_id,
        model_id=resolved.model.id,
        model_policy=metadata.model_policy,
        batch_job_id=context.job_id,
    )
    await _update_item_progress(context.session, item, current=3, total=3, message="章节摘要完成")
    await _publish_item_progress(
        context,
        item,
        row,
        current=3,
        total=3,
        message="章节摘要完成",
    )
    await _mark_item_terminal(context.session, item, JOB_STATUS_SUCCEEDED)
    await _publish_item_terminal(context, item, row, terminal_status="succeeded")


async def _process_long_term_item(context: JobContext, item: BackgroundJobItem, metadata: SummaryBatchContext) -> None:
    payload = job_service.parse_json_object(item.payload_json)
    project_id = payload.get("project_id")
    start_order = payload.get("start_order")
    end_order = payload.get("end_order")
    if not isinstance(project_id, str) or not isinstance(start_order, int) or not isinstance(end_order, int):
        raise ValueError("长期摘要 item 缺少区间信息")

    source = await summary_service.load_long_term_source(context.session, project_id, start_order, end_order)
    if len(source) < summary_service.LONG_TERM_SUMMARY_INTERVAL:
        row = await summary_service.create_or_update_long_term_summary(
            context.session,
            project_id,
            source,
            status=summary_service.SUMMARY_STATUS_FAILED,
            source_chapter_ids=await summary_service.load_long_term_chapter_ids(context.session, project_id, start_order, end_order),
            job_id=item.id,
        )
        await summary_service.mark_summary_failed(context.session, row, "可聚合章节摘要不足")
        await summary_service.publish_long_term_summary_update(context, row)
        await _mark_item_terminal(context.session, item, JOB_STATUS_SKIPPED, error_message="可聚合章节摘要不足")
        await _publish_item_terminal(
            context,
            item,
            row,
            terminal_status="skipped",
            error_message="可聚合章节摘要不足",
        )
        return

    chapters = await chapter_repo.list_by_project(context.session, project_id)
    try:
        resolved = await resolve_background_llm(
            context.session,
            model_policy=str(payload.get("model_policy") or metadata.model_policy),
            model_id=str(payload.get("model_id")) if isinstance(payload.get("model_id"), str) else metadata.model_id,
        )
    except BackgroundModelUnavailableError as exc:
        row = await summary_service.create_or_update_long_term_summary(
            context.session,
            project_id,
            source,
            status=summary_service.SUMMARY_STATUS_FAILED,
            source_chapter_ids=await summary_service.load_long_term_chapter_ids(context.session, project_id, start_order, end_order),
            job_id=item.id,
        )
        await summary_service.mark_summary_failed(context.session, row, str(exc))
        await summary_service.publish_long_term_summary_update(context, row)
        await _mark_item_terminal(context.session, item, JOB_STATUS_SKIPPED, error_message=str(exc))
        await _publish_item_terminal(
            context,
            item,
            row,
            terminal_status="skipped",
            error_message=str(exc),
        )
        return

    row = await summary_service.create_or_update_long_term_summary(
        context.session,
        project_id,
        source,
        status=summary_service.SUMMARY_STATUS_RUNNING,
        source_chapter_ids=await summary_service.load_long_term_chapter_ids(context.session, project_id, start_order, end_order),
        job_id=item.id,
        model_id=resolved.model.id,
    )
    await summary_service.publish_long_term_summary_update(context, row)
    await _update_item_progress(context.session, item, current=1, total=3, message="正在生成区间摘要")
    await _publish_item_progress(
        context,
        item,
        row,
        current=1,
        total=3,
        message="正在生成区间摘要",
    )
    await _update_batch_progress(context.session, context, message="正在生成区间摘要")
    await job_service.commit_and_notify(context.session)
    prompt = await summary_generator.build_long_term_summary_prompt(context.session, source, chapters)
    result = await summary_generator.generate_long_term_summary_from_prompt(resolved.client, prompt)
    refreshed_source = await summary_service.load_long_term_source(context.session, project_id, start_order, end_order)
    row = await summary_service.save_long_term_summary_result(
        context.session,
        project_id,
        refreshed_source,
        start_time=result.start_time,
        end_time=result.end_time,
        summary=result.summary,
        token_count=result.token_count,
        model_id=resolved.model.id,
        job_id=item.id,
        source_chapter_ids=await summary_service.load_long_term_chapter_ids(context.session, project_id, start_order, end_order),
    )
    await _update_item_progress(context.session, item, current=2, total=3, message="区间摘要已保存")
    await _publish_item_progress(
        context,
        item,
        row,
        current=2,
        total=3,
        message="区间摘要已保存",
    )
    await summary_service.publish_long_term_summary_update(context, row)
    await _update_item_progress(context.session, item, current=3, total=3, message="区间摘要完成")
    await _publish_item_progress(
        context,
        item,
        row,
        current=3,
        total=3,
        message="区间摘要完成",
    )
    await _mark_item_terminal(context.session, item, JOB_STATUS_SUCCEEDED)
    await _publish_item_terminal(context, item, row, terminal_status="succeeded")


async def handle_summary_batch(context: JobContext) -> dict[str, int] | None:
    SummaryBatchInput.model_validate(context.input)
    metadata = SummaryBatchContext.model_validate(context.metadata)
    batch_job_id = context.job_id

    while True:
        await context.check_cancelled()
        items = await job_service.list_job_items(context.session, job_id=batch_job_id)
        pending_item = next((item for item in items if item.status == JOB_STATUS_PENDING), None)
        if pending_item is None:
            break
        pending_item = await _mark_item_running(context.session, pending_item)
        try:
            if pending_item.type == summary_service.SUMMARY_BATCH_ITEM_TYPE_CHAPTER:
                await _process_chapter_item(context, pending_item, metadata)
            elif pending_item.type == summary_service.SUMMARY_BATCH_ITEM_TYPE_LONG_TERM:
                await _process_long_term_item(context, pending_item, metadata)
            else:
                raise ValueError(f"未知摘要队列项类型: {pending_item.type}")
        except Exception as exc:
            payload = job_service.parse_json_object(pending_item.payload_json)
            summary_row = None
            if pending_item.type == summary_service.SUMMARY_BATCH_ITEM_TYPE_CHAPTER:
                chapter_id = payload.get("chapter_id")
                if isinstance(chapter_id, str):
                    summary = await summary_service.get_chapter_summary(context.session, chapter_id)
                    if summary is not None:
                        summary_row = await summary_service.mark_summary_failed(context.session, summary, str(exc))
                        await summary_service.publish_chapter_summary_update(context, summary_row)
            elif pending_item.type == summary_service.SUMMARY_BATCH_ITEM_TYPE_LONG_TERM:
                project_id = payload.get("project_id")
                start_order = payload.get("start_order")
                end_order = payload.get("end_order")
                if isinstance(project_id, str) and isinstance(start_order, int) and isinstance(end_order, int):
                    long_term_row = await summary_service.get_long_term_summary_by_range(
                        context.session,
                        project_id,
                        start_order,
                        end_order,
                    )
                    if long_term_row is not None:
                        summary_row = await summary_service.mark_summary_failed(
                            context.session,
                            long_term_row,
                            str(exc),
                        )
                        await summary_service.publish_long_term_summary_update(context, summary_row)
            await _mark_item_terminal(context.session, pending_item, JOB_STATUS_FAILED, error_message=str(exc))
            if summary_row is not None:
                await _publish_item_terminal(
                    context,
                    pending_item,
                    summary_row,
                    terminal_status="failed",
                    error_message=str(exc),
                )
        await _update_batch_progress(context.session, context)
        await job_service.commit_and_notify(context.session)

    items = await job_service.list_job_items(context.session, job_id=batch_job_id)
    return {
        "total": len(items),
        "succeeded": sum(1 for item in items if item.status == JOB_STATUS_SUCCEEDED),
        "failed": sum(1 for item in items if item.status == JOB_STATUS_FAILED),
        "skipped": sum(1 for item in items if item.status == JOB_STATUS_SKIPPED),
    }


async def _finalize_incomplete_batch_items(context: JobContext, reason: str) -> None:
    items = await job_service.list_job_items(context.session, job_id=context.job_id)
    for item in items:
        if item.status not in {JOB_STATUS_PENDING, JOB_STATUS_RUNNING}:
            continue
        await _mark_item_terminal(context.session, item, JOB_STATUS_FAILED, error_message=reason)
        payload = job_service.parse_json_object(item.payload_json)
        if item.type == summary_service.SUMMARY_BATCH_ITEM_TYPE_CHAPTER:
            chapter_id = payload.get("chapter_id")
            if not isinstance(chapter_id, str):
                continue
            summary = await summary_service.get_chapter_summary(context.session, chapter_id)
            if summary is None or summary.status not in {
                summary_service.SUMMARY_STATUS_QUEUED,
                summary_service.SUMMARY_STATUS_RUNNING,
            }:
                continue
            summary = await summary_service.mark_summary_failed(context.session, summary, reason)
            await summary_service.publish_chapter_summary_update(context, summary)
            await _publish_item_terminal(
                context,
                item,
                summary,
                terminal_status="failed",
                error_message=reason,
            )
            continue
        if item.type != summary_service.SUMMARY_BATCH_ITEM_TYPE_LONG_TERM:
            continue
        project_id = payload.get("project_id")
        start_order = payload.get("start_order")
        end_order = payload.get("end_order")
        if not isinstance(project_id, str) or not isinstance(start_order, int) or not isinstance(end_order, int):
            continue
        summary = await summary_service.get_long_term_summary_by_range(
            context.session,
            project_id,
            start_order,
            end_order,
        )
        if summary is None or summary.status not in {
            summary_service.SUMMARY_STATUS_QUEUED,
            summary_service.SUMMARY_STATUS_RUNNING,
        }:
            continue
        summary = await summary_service.mark_summary_failed(context.session, summary, reason)
        await summary_service.publish_long_term_summary_update(context, summary)
        await _publish_item_terminal(
            context,
            item,
            summary,
            terminal_status="failed",
            error_message=reason,
        )


async def _handle_summary_batch_failed(context: JobContext, reason: str) -> None:
    await _finalize_incomplete_batch_items(context, reason)


async def _handle_summary_batch_timeout(context: JobContext, reason: str) -> None:
    await _finalize_incomplete_batch_items(context, reason)


async def _handle_summary_batch_cancelled(context: JobContext, reason: str) -> None:
    await _finalize_incomplete_batch_items(context, reason)


SUMMARY_BATCH_JOB = JobDefinition(
    type=JOB_TYPE_SUMMARY_BATCH,
    name="Summary batch",
    description="Run unified chapter and long-term summary queue items.",
    input_model=SummaryBatchInput,
    handler=handle_summary_batch,
    on_failed=_handle_summary_batch_failed,
    on_timeout=_handle_summary_batch_timeout,
    on_cancelled=_handle_summary_batch_cancelled,
    default_queue=JOB_QUEUE_LLM,
    default_timeout_seconds=900,
    default_max_attempts=1,
    supports_cancel=True,
)
