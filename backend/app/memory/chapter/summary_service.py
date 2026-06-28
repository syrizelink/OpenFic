# -*- coding: utf-8 -*-
"""Summary scheduling and status service."""

import hashlib
import json
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.background.events.publisher import BackgroundEventPublisher
from app.background.jobs import service as job_service
from app.background.jobs.constants import JOB_TYPE_SUMMARY_BATCH
from app.background.jobs.models import BackgroundJob
from app.background.jobs.models import BackgroundJobItem
from app.background.jobs.states import (
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
    JOB_STATUS_SKIPPED,
    JOB_STATUS_SUCCEEDED,
)
from app.core.errors import NotFoundError, ValidationError
from app.memory.chapter.sequence import global_order_index
from app.storage.models.chapter import Chapter
from app.storage.models.chapter_summary import ChapterSummary
from app.storage.models.volume import Volume
from app.storage.repos import chapter_repo, chapter_summary_repo, volume_repo
from app.storage.repos.chapter_summary_repo import (
    SUMMARY_STATUS_FAILED,
    SUMMARY_STATUS_NOT_GENERATED,
    SUMMARY_STATUS_QUEUED,
    SUMMARY_STATUS_READY,
    SUMMARY_STATUS_RUNNING,
    SUMMARY_TYPE_CHAPTER,
    SUMMARY_TYPE_LONG_TERM,
)

CHAPTER_SUMMARY_INTERVAL = 10
LONG_TERM_SUMMARY_INTERVAL = 10
AUTO_GENERATION_BLOCK_CHAPTER_THRESHOLD = 20
MIN_CHAPTER_SUMMARY_WORD_COUNT = 500
SUMMARY_STALE_DIFF_THRESHOLD = 100
SUMMARY_BATCH_ITEM_TYPE_CHAPTER = "chapter_summary"
SUMMARY_BATCH_ITEM_TYPE_LONG_TERM = "long_term_summary"
SUMMARY_BATCH_ITEM_PROGRESS_TOTAL = 3


def get_background_supervisor():
    from app.background.runtime.supervisor import get_background_supervisor as _get_background_supervisor

    return _get_background_supervisor()


@dataclass(frozen=True)
class ActiveSummaryJob:
    job_id: str
    job_type: str
    status: str
    chapter_id: str | None
    summary_id: str | None
    start_order: int | None
    end_order: int | None
    progress_current: int
    progress_total: int | None
    progress_message: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class LongTermSummaryWindow:
    start_order: int
    end_order: int
    chapter_ids: list[str]
    source_summaries: list[ChapterSummary]


def build_summary_batch_item_event_payload(
    *,
    project_id: str,
    status: str,
    summary_id: str | None,
    chapter_id: str | None = None,
    start_order: int | None = None,
    end_order: int | None = None,
    is_stale: bool = False,
    progress_current: int = 0,
    progress_total: int | None = SUMMARY_BATCH_ITEM_PROGRESS_TOTAL,
    progress_message: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "project_id": project_id,
        "status": status,
        "summary_id": summary_id,
        "is_stale": is_stale,
        "progress_current": progress_current,
        "progress_total": progress_total,
        "progress_message": progress_message,
        "error_message": error_message,
    }
    if chapter_id is not None:
        payload["chapter_id"] = chapter_id
    if start_order is not None:
        payload["start_order"] = start_order
    if end_order is not None:
        payload["end_order"] = end_order
    return payload


async def publish_summary_batch_item_event(
    session: AsyncSession,
    job: BackgroundJob,
    *,
    event_type: str,
    item_id: str,
    item_type: str,
    payload: dict[str, Any],
    publisher: BackgroundEventPublisher | None = None,
) -> None:
    resolved_publisher = publisher or get_background_supervisor().create_event_publisher()
    await job_service.append_event(
        session,
        resolved_publisher,
        job,
        event_type=event_type,
        payload=payload,
        item_id=item_id,
        item_type=item_type,
    )


def parse_summary_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if str(item).strip()]


def encode_summary_list(value: list[str]) -> str:
    return json.dumps(value, ensure_ascii=False)


def is_chapter_summary_skipped(chapter: Chapter) -> bool:
    return chapter.word_count < MIN_CHAPTER_SUMMARY_WORD_COUNT


def is_chapter_summary_stale(summary: ChapterSummary | None, chapter: Chapter) -> bool:
    if summary is None or summary.status != SUMMARY_STATUS_READY:
        return False
    return _diff_character_count(
        summary.source_content_normalized,
        normalize_summary_source_content(chapter.content),
    ) > SUMMARY_STALE_DIFF_THRESHOLD


def normalize_summary_source_content(content: str) -> str:
    return "".join(
        char
        for char in content
        if not char.isspace() and not unicodedata.category(char).startswith("P")
    )


def _diff_character_count(left: str, right: str) -> int:
    matcher = SequenceMatcher(a=left, b=right, autojunk=False)
    count = 0
    for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        count += (left_end - left_start) + (right_end - right_start)
    return count


def chapter_summary_signature(summary: ChapterSummary) -> str:
    payload = json.dumps(
        {
            "chapter_id": summary.chapter_id,
            "source": summary.source_content_normalized,
            "summary": summary.summary,
            "start_time": summary.start_time,
            "end_time": summary.end_time,
            "characters": summary.characters_json,
            "locations": summary.locations_json,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _source_chapter_ids(source_summaries: list[ChapterSummary]) -> list[str]:
    return [summary.chapter_id for summary in source_summaries if summary.chapter_id]


def _window_source_chapter_ids(source_summaries: list[ChapterSummary]) -> list[str]:
    return [
        summary.chapter_id
        for summary in sorted(source_summaries, key=lambda item: item.chapter_order or 0)
        if summary.chapter_id
    ]


def _source_chapter_summary_signatures(source_summaries: list[ChapterSummary]) -> list[str]:
    return [
        chapter_summary_signature(summary)
        for summary in sorted(source_summaries, key=lambda item: item.chapter_order or 0)
    ]


def is_long_term_summary_stale(
    summary: ChapterSummary | None,
    chapters: list[Chapter],
    chapter_summaries: list[ChapterSummary],
    volumes: list[Volume],
) -> bool:
    if summary is None or summary.status != SUMMARY_STATUS_READY:
        return False
    if summary.start_order is None or summary.end_order is None:
        return True
    window = build_long_term_summary_window(
        chapters,
        volumes,
        chapter_summaries,
        summary.start_order,
        summary.end_order,
    )
    if window is None:
        return True
    saved_chapter_ids = parse_summary_list(summary.source_chapter_ids_json)
    saved_signatures = parse_summary_list(summary.source_chapter_summary_signatures_json)
    current_signatures = _source_chapter_summary_signatures(window.source_summaries)
    return saved_chapter_ids != window.chapter_ids or saved_signatures != current_signatures


def _fixed_summary_windows(
    chapters: list[Chapter],
    volumes: list[Volume],
    size: int,
) -> list[list[Chapter]]:
    order_map = global_order_index(chapters, volumes)
    ordered = sorted(chapters, key=lambda chapter: order_map.get(chapter.id, float("inf")))
    windows: list[list[Chapter]] = []
    for start in range(1, len(ordered) + 1, size):
        group = [
            chapter
            for chapter in ordered
            if start <= order_map[chapter.id] < start + size
        ]
        if len(group) == size:
            windows.append(group)
    return windows


def _build_long_term_window_from_group(
    chapter_group: list[Chapter],
    volumes: list[Volume],
    summary_by_chapter_id: dict[str | None, ChapterSummary],
) -> LongTermSummaryWindow | None:
    order_map = global_order_index(chapter_group, volumes)
    source_summaries: list[ChapterSummary] = []
    for chapter in sorted(chapter_group, key=lambda item: order_map.get(item.id, float("inf"))):
        if is_chapter_summary_skipped(chapter):
            continue
        summary = summary_by_chapter_id.get(chapter.id)
        if summary is None or summary.status != SUMMARY_STATUS_READY:
            return None
        source_summaries.append(summary)
    if not source_summaries:
        return None
    ordered_chapters = sorted(chapter_group, key=lambda item: order_map.get(item.id, float("inf")))
    return LongTermSummaryWindow(
        start_order=order_map[ordered_chapters[0].id],
        end_order=order_map[ordered_chapters[-1].id],
        chapter_ids=[chapter.id for chapter in ordered_chapters],
        source_summaries=source_summaries,
    )


def build_long_term_summary_window(
    chapters: list[Chapter],
    volumes: list[Volume],
    chapter_summaries: list[ChapterSummary],
    start_order: int,
    end_order: int,
) -> LongTermSummaryWindow | None:
    summary_by_chapter_id = {summary.chapter_id: summary for summary in chapter_summaries}
    order_map = global_order_index(chapters, volumes)
    chapter_group = [
        chapter
        for chapter in chapters
        if start_order <= order_map.get(chapter.id, -1) <= end_order
    ]
    if len(chapter_group) != end_order - start_order + 1:
        return None
    return _build_long_term_window_from_group(chapter_group, volumes, summary_by_chapter_id)


def list_eligible_long_term_ranges(
    chapters: list[Chapter],
    volumes: list[Volume],
    chapter_summaries: list[ChapterSummary],
) -> list[tuple[int, int]]:
    summary_by_chapter_id = {summary.chapter_id: summary for summary in chapter_summaries}
    ranges: list[tuple[int, int]] = []
    for chapter_group in _fixed_summary_windows(chapters, volumes, LONG_TERM_SUMMARY_INTERVAL):
        window = _build_long_term_window_from_group(chapter_group, volumes, summary_by_chapter_id)
        if window is None:
            continue
        ranges.append((window.start_order, window.end_order))
    return ranges


def list_ready_unaggregated_long_term_windows(
    chapters: list[Chapter],
    volumes: list[Volume],
    chapter_summaries: list[ChapterSummary],
    long_term_summaries: list[ChapterSummary],
) -> list[LongTermSummaryWindow]:
    summary_by_chapter_id = {summary.chapter_id: summary for summary in chapter_summaries}
    long_term_by_range = {
        (summary.start_order, summary.end_order): summary
        for summary in long_term_summaries
        if summary.start_order is not None and summary.end_order is not None
    }
    windows: list[LongTermSummaryWindow] = []
    for chapter_group in _fixed_summary_windows(chapters, volumes, LONG_TERM_SUMMARY_INTERVAL):
        window = _build_long_term_window_from_group(chapter_group, volumes, summary_by_chapter_id)
        if window is None:
            continue
        existing = long_term_by_range.get((window.start_order, window.end_order))
        if existing is not None and not is_long_term_summary_stale(
            existing, chapters, chapter_summaries, volumes
        ):
            continue
        windows.append(window)
    return windows


async def list_chapter_summaries(
    session: AsyncSession, project_id: str
) -> list[ChapterSummary]:
    return await chapter_summary_repo.list_chapter_summaries_by_project(session, project_id)


async def list_long_term_summaries(
    session: AsyncSession, project_id: str
) -> list[ChapterSummary]:
    return await chapter_summary_repo.list_long_term_summaries_by_project(
        session, project_id
    )


async def get_chapter_summary(
    session: AsyncSession, chapter_id: str
) -> ChapterSummary | None:
    return await chapter_summary_repo.get_by_chapter_id(session, chapter_id)


async def get_summary_status_map(session: AsyncSession, project_id: str) -> dict[str, str]:
    chapters = await chapter_repo.list_by_project(session, project_id)
    summaries = await list_chapter_summaries(session, project_id)
    summary_by_chapter_id = {summary.chapter_id: summary for summary in summaries}
    return {
        chapter.id: summary.status
        if (summary := summary_by_chapter_id.get(chapter.id)) is not None
        else SUMMARY_STATUS_NOT_GENERATED
        for chapter in chapters
    }


async def ensure_chapter_summary_row(
    session: AsyncSession,
    chapter: Chapter,
    *,
    status: str,
    job_id: str | None = None,
    model_id: str | None = None,
) -> ChapterSummary:
    existing = await chapter_summary_repo.get_by_chapter_id(session, chapter.id)
    now = datetime.now(UTC)
    chapters = await chapter_repo.list_by_project(session, chapter.project_id)
    volumes = await volume_repo.list_by_project(session, chapter.project_id)
    order_map = global_order_index(chapters, volumes)
    global_order = order_map.get(chapter.id, chapter.order)
    if existing is None:
        return await chapter_summary_repo.create(
            session,
            ChapterSummary(
                project_id=chapter.project_id,
                summary_type=SUMMARY_TYPE_CHAPTER,
                status=status,
                chapter_id=chapter.id,
                volume_id=chapter.volume_id,
                chapter_order=global_order,
                start_order=global_order,
                end_order=global_order,
                job_id=job_id,
                model_id=model_id,
                created_at=now,
                updated_at=now,
            ),
        )

    existing.status = status
    existing.volume_id = chapter.volume_id
    existing.chapter_order = global_order
    existing.start_order = global_order
    existing.end_order = global_order
    existing.job_id = job_id
    existing.model_id = model_id or existing.model_id
    existing.error_message = None
    return await chapter_summary_repo.update(session, existing)


async def mark_chapter_summary_running(
    session: AsyncSession, chapter_id: str, job_id: str, model_id: str | None
) -> ChapterSummary:
    chapter = await chapter_repo.get_by_id(session, chapter_id)
    if chapter is None:
        raise NotFoundError(f"章节不存在: {chapter_id}")
    return await ensure_chapter_summary_row(
        session,
        chapter,
        status=SUMMARY_STATUS_RUNNING,
        job_id=job_id,
        model_id=model_id,
    )


async def save_chapter_summary_result(
    session: AsyncSession,
    chapter_id: str,
    *,
    start_time: str,
    end_time: str,
    characters: list[str],
    locations: list[str],
    summary: str,
    token_count: int,
    model_id: str | None,
    job_id: str | None,
) -> ChapterSummary:
    chapter = await chapter_repo.get_by_id(session, chapter_id)
    if chapter is None:
        raise NotFoundError(f"章节不存在: {chapter_id}")
    row = await ensure_chapter_summary_row(
        session,
        chapter,
        status=SUMMARY_STATUS_READY,
        job_id=job_id,
        model_id=model_id,
    )
    row.start_time = start_time
    row.end_time = end_time
    row.characters_json = encode_summary_list(characters)
    row.locations_json = encode_summary_list(locations)
    row.summary = summary
    row.token_count = token_count
    row.error_message = None
    row.source_content_normalized = normalize_summary_source_content(chapter.content)
    return await chapter_summary_repo.update(session, row)


async def mark_summary_failed(
    session: AsyncSession, summary: ChapterSummary, error_message: str
) -> ChapterSummary:
    summary.status = SUMMARY_STATUS_FAILED
    summary.error_message = error_message[:2000]
    return await chapter_summary_repo.update(session, summary)


async def create_or_update_long_term_summary(
    session: AsyncSession,
    project_id: str,
    source_summaries: list[ChapterSummary],
    *,
    status: str,
    source_chapter_ids: list[str] | None = None,
    job_id: str | None = None,
    model_id: str | None = None,
) -> ChapterSummary:
    if not source_summaries:
        raise NotFoundError("没有可聚合的章节摘要")
    start_order = min(summary.chapter_order or 0 for summary in source_summaries)
    end_order = max(summary.chapter_order or 0 for summary in source_summaries)
    source_chapter_ids_json = encode_summary_list(
        source_chapter_ids
        if source_chapter_ids is not None
        else _window_source_chapter_ids(source_summaries)
    )
    source_signatures_json = encode_summary_list(_source_chapter_summary_signatures(source_summaries))
    existing = await chapter_summary_repo.get_long_term_by_range(
        session, project_id, start_order, end_order
    )
    now = datetime.now(UTC)
    if existing is None:
        return await chapter_summary_repo.create(
            session,
            ChapterSummary(
                project_id=project_id,
                summary_type=SUMMARY_TYPE_LONG_TERM,
                status=status,
                start_order=start_order,
                end_order=end_order,
                source_chapter_ids_json=source_chapter_ids_json,
                source_chapter_summary_signatures_json=source_signatures_json,
                job_id=job_id,
                model_id=model_id,
                created_at=now,
                updated_at=now,
            ),
        )
    existing.status = status
    existing.start_order = start_order
    existing.end_order = end_order
    existing.source_chapter_ids_json = source_chapter_ids_json
    existing.source_chapter_summary_signatures_json = source_signatures_json
    existing.job_id = job_id
    existing.model_id = model_id or existing.model_id
    existing.error_message = None
    return await chapter_summary_repo.update(session, existing)


async def save_long_term_summary_result(
    session: AsyncSession,
    project_id: str,
    source_summaries: list[ChapterSummary],
    *,
    start_time: str,
    end_time: str,
    summary: str,
    token_count: int,
    model_id: str | None,
    job_id: str | None,
    source_chapter_ids: list[str] | None = None,
) -> ChapterSummary:
    row = await create_or_update_long_term_summary(
        session,
        project_id,
        source_summaries,
        status=SUMMARY_STATUS_READY,
        source_chapter_ids=source_chapter_ids,
        job_id=job_id,
        model_id=model_id,
    )
    row.start_time = start_time
    row.end_time = end_time
    row.summary = summary
    row.token_count = token_count
    row.error_message = None
    return await chapter_summary_repo.update(session, row)


async def get_long_term_summary_by_range(
    session: AsyncSession,
    project_id: str,
    start_order: int,
    end_order: int,
) -> ChapterSummary | None:
    return await chapter_summary_repo.get_long_term_by_range(
        session,
        project_id,
        start_order,
        end_order,
    )


async def load_long_term_chapter_ids(
    session: AsyncSession,
    project_id: str,
    start_order: int,
    end_order: int,
) -> list[str]:
    chapters = await chapter_repo.list_by_project(session, project_id)
    volumes = await volume_repo.list_by_project(session, project_id)
    order_map = global_order_index(chapters, volumes)
    return [
        chapter.id
        for chapter in chapters
        if start_order <= order_map.get(chapter.id, -1) <= end_order
    ]


async def load_long_term_source(
    session: AsyncSession,
    project_id: str,
    start_order: int,
    end_order: int,
) -> list[ChapterSummary]:
    chapter_ids = await load_long_term_chapter_ids(session, project_id, start_order, end_order)
    summaries = await chapter_summary_repo.list_chapter_summaries_by_chapter_ids(
        session,
        chapter_ids,
        ready_only=True,
    )
    return sorted(summaries, key=lambda summary: summary.chapter_order or 0)


async def _job_item_progress_message(session: AsyncSession, item_id: str | None) -> str | None:
    if item_id is None:
        return None
    items = await job_service.list_job_items_by_ids(session, item_ids=[item_id])
    if not items:
        return None
    progress = job_service.parse_json_object(items[0].progress_json)
    message = progress.get("message")
    return message if isinstance(message, str) else None


async def publish_chapter_summary_update(context, row: ChapterSummary) -> None:
    await job_service.append_event(
        context.session,
        context.publisher,
        context.job,
        job_id=context.job_id,
        job_type=context.job_type,
        subject_type=context.subject_type,
        subject_id=context.subject_id,
        event_type="chapter_summary_updated",
        payload={
            "project_id": row.project_id,
            "chapter_id": row.chapter_id,
            "summary_id": row.id,
            "status": row.status,
            "is_stale": False,
            "progress_message": await _job_item_progress_message(context.session, row.job_id),
            "error_message": row.error_message,
            "updated_at": row.updated_at.isoformat(),
        },
        item_id=row.job_id,
        item_type="chapter_summary",
    )


async def publish_long_term_summary_update(context, row: ChapterSummary) -> None:
    await job_service.append_event(
        context.session,
        context.publisher,
        context.job,
        job_id=context.job_id,
        job_type=context.job_type,
        subject_type=context.subject_type,
        subject_id=context.subject_id,
        event_type="long_term_summary_updated",
        payload={
            "project_id": row.project_id,
            "summary_id": row.id,
            "status": row.status,
            "start_order": row.start_order,
            "end_order": row.end_order,
            "is_stale": False,
            "progress_message": await _job_item_progress_message(context.session, row.job_id),
            "error_message": row.error_message,
            "updated_at": row.updated_at.isoformat(),
        },
        item_id=row.job_id,
        item_type="long_term_summary",
    )


@dataclass(frozen=True)
class SummaryBatchAppendResult:
    batch_job_id: str
    item_ids: list[str]
    chapter_summary_ids: list[str]
    long_term_summary_ids: list[str]


async def list_all_missing_summary_ranges(
    session: AsyncSession,
    project_id: str,
) -> tuple[list[str], list[tuple[int, int]]]:
    chapters = await chapter_repo.list_by_project(session, project_id)
    volumes = await volume_repo.list_by_project(session, project_id)
    chapter_summaries = await list_chapter_summaries(session, project_id)
    long_term_summaries = await list_long_term_summaries(session, project_id)
    summary_by_chapter_id = {summary.chapter_id: summary for summary in chapter_summaries}
    chapter_ids: list[str] = []
    for chapter in chapters:
        if is_chapter_summary_skipped(chapter):
            continue
        summary = summary_by_chapter_id.get(chapter.id)
        if summary is None or summary.status == SUMMARY_STATUS_FAILED or is_chapter_summary_stale(summary, chapter):
            chapter_ids.append(chapter.id)
    ranges: list[tuple[int, int]] = []
    long_term_by_range = {
        (summary.start_order, summary.end_order): summary
        for summary in long_term_summaries
        if summary.start_order is not None and summary.end_order is not None
    }
    for start_order, end_order in list_eligible_long_term_ranges(chapters, volumes, chapter_summaries):
        existing = long_term_by_range.get((start_order, end_order))
        if existing is None or existing.status == SUMMARY_STATUS_FAILED or is_long_term_summary_stale(existing, chapters, chapter_summaries, volumes):
            ranges.append((start_order, end_order))
    return chapter_ids, ranges


def _chapter_item_key(chapter_id: str) -> str:
    return f"chapter:{chapter_id}"


def _long_term_item_key(start_order: int, end_order: int) -> str:
    return f"long_term:{start_order}:{end_order}"


async def _get_or_create_summary_batch_job(
    session: AsyncSession,
    project_id: str,
    *,
    model_id: str | None,
    model_policy: str,
) -> tuple[BackgroundJob, bool]:
    existing = await job_service.list_jobs(
        session,
        subject_type="project",
        subject_id=project_id,
        statuses={JOB_STATUS_PENDING, JOB_STATUS_RUNNING},
        job_types={JOB_TYPE_SUMMARY_BATCH},
        limit=1,
        offset=0,
    )
    if existing:
        return cast(BackgroundJob, existing[0]), False
    job = await job_service.submit_job(
        session,
        job_type=JOB_TYPE_SUMMARY_BATCH,
        payload={"project_id": project_id},
        context={
            "project_id": project_id,
            "model_id": model_id,
            "model_policy": model_policy,
        },
        subject_type="project",
        subject_id=project_id,
    )
    return cast(BackgroundJob, job), True


async def _existing_batch_item_map(session: AsyncSession, batch_job_id: str) -> dict[str, BackgroundJobItem]:
    items = await job_service.list_job_items(session, job_id=batch_job_id)
    return {
        item.item_key: item
        for item in items
        if item.status not in {JOB_STATUS_SUCCEEDED, JOB_STATUS_SKIPPED}
    }


async def _append_batch_item(
    session: AsyncSession,
    *,
    batch_job_id: str,
    order_index: int,
    item_key: str,
    item_type: str,
    payload: dict[str, object],
) -> BackgroundJobItem:
    return await job_service.create_item(
        session,
        job_id=batch_job_id,
        item_key=item_key,
        item_type=item_type,
        payload=payload,
        order_index=order_index,
    )


async def _publish_batch_item_queued_event(
    session: AsyncSession,
    batch_job: BackgroundJob,
    *,
    item: BackgroundJobItem,
    item_type: str,
    project_id: str,
    summary_id: str | None,
    chapter_id: str | None = None,
    start_order: int | None = None,
    end_order: int | None = None,
    publisher: BackgroundEventPublisher | None = None,
) -> None:
    await publish_summary_batch_item_event(
        session,
        batch_job,
        event_type="background_item_queued",
        item_id=item.id,
        item_type=item_type,
        payload=build_summary_batch_item_event_payload(
            project_id=project_id,
            status=SUMMARY_STATUS_QUEUED,
            summary_id=summary_id,
            chapter_id=chapter_id,
            start_order=start_order,
            end_order=end_order,
            is_stale=False,
            progress_current=0,
            progress_total=SUMMARY_BATCH_ITEM_PROGRESS_TOTAL,
            progress_message="已加入队列",
            error_message=None,
        ),
        publisher=publisher,
    )


async def append_chapter_summary_items(
    session: AsyncSession,
    project_id: str,
    chapter_ids: list[str],
    *,
    model_id: str | None = None,
    model_policy: str = "light_model",
) -> SummaryBatchAppendResult:
    if not chapter_ids:
        raise ValidationError("没有可加入队列的章节摘要")
    batch_job, created = await _get_or_create_summary_batch_job(
        session,
        project_id,
        model_id=model_id,
        model_policy=model_policy,
    )
    existing_map = await _existing_batch_item_map(session, batch_job.id)
    order_index = len(await job_service.list_job_items(session, job_id=batch_job.id))
    item_ids: list[str] = []
    summary_ids: list[str] = []
    for chapter_id in chapter_ids:
        chapter = await chapter_repo.get_by_id(session, chapter_id)
        if chapter is None or chapter.project_id != project_id:
            raise NotFoundError(f"章节不存在: {chapter_id}")
        if is_chapter_summary_skipped(chapter):
            raise ValidationError(f"章节字数不足 {MIN_CHAPTER_SUMMARY_WORD_COUNT}，不能生成摘要")
        key = _chapter_item_key(chapter_id)
        existing_item = existing_map.get(key)
        current_row = await chapter_summary_repo.get_by_chapter_id(session, chapter_id)
        is_ready_and_fresh = (
            current_row is not None
            and current_row.status == SUMMARY_STATUS_READY
            and not is_chapter_summary_stale(current_row, chapter)
        )
        if is_ready_and_fresh:
            if current_row is not None:
                summary_ids.append(current_row.id)
            if existing_item is not None:
                item_ids.append(existing_item.id)
            continue
        if current_row is not None and current_row.status == SUMMARY_STATUS_READY:
            row = current_row
        else:
            row = await ensure_chapter_summary_row(
                session,
                chapter,
                status=SUMMARY_STATUS_QUEUED,
                model_id=model_id,
            )
        if existing_item is not None:
            if row.status != SUMMARY_STATUS_READY:
                row.job_id = existing_item.id
                await chapter_summary_repo.update(session, row)
            item_ids.append(existing_item.id)
            summary_ids.append(row.id)
            await _publish_batch_item_queued_event(
                session,
                batch_job,
                item=existing_item,
                item_type=SUMMARY_BATCH_ITEM_TYPE_CHAPTER,
                project_id=project_id,
                summary_id=row.id,
                chapter_id=chapter_id,
            )
            continue
        item = await _append_batch_item(
            session,
            batch_job_id=batch_job.id,
            order_index=order_index,
            item_key=key,
            item_type=SUMMARY_BATCH_ITEM_TYPE_CHAPTER,
            payload={
                "project_id": project_id,
                "chapter_id": chapter_id,
                "model_id": model_id,
                "model_policy": model_policy,
            },
        )
        order_index += 1
        if row.status != SUMMARY_STATUS_READY:
            row.job_id = item.id
            await chapter_summary_repo.update(session, row)
        item_ids.append(item.id)
        summary_ids.append(row.id)
        await _publish_batch_item_queued_event(
            session,
            batch_job,
            item=item,
            item_type=SUMMARY_BATCH_ITEM_TYPE_CHAPTER,
            project_id=project_id,
            summary_id=row.id,
            chapter_id=chapter_id,
        )
    if created:
        return SummaryBatchAppendResult(batch_job.id, item_ids, summary_ids, [])
    return SummaryBatchAppendResult(batch_job.id, item_ids, summary_ids, [])


async def append_long_term_summary_items(
    session: AsyncSession,
    project_id: str,
    ranges: list[tuple[int, int]],
    *,
    model_id: str | None = None,
    model_policy: str = "light_model",
) -> SummaryBatchAppendResult:
    if not ranges:
        raise ValidationError("没有可加入队列的区间摘要")
    batch_job, created = await _get_or_create_summary_batch_job(
        session,
        project_id,
        model_id=model_id,
        model_policy=model_policy,
    )
    existing_map = await _existing_batch_item_map(session, batch_job.id)
    order_index = len(await job_service.list_job_items(session, job_id=batch_job.id))
    item_ids: list[str] = []
    summary_ids: list[str] = []
    chapters = await chapter_repo.list_by_project(session, project_id)
    volumes = await volume_repo.list_by_project(session, project_id)
    chapter_summaries = await list_chapter_summaries(session, project_id)
    existing_long_term_by_range = {
        (summary.start_order, summary.end_order): summary
        for summary in await list_long_term_summaries(session, project_id)
        if summary.start_order is not None and summary.end_order is not None
    }
    for start_order, end_order in ranges:
        window = build_long_term_summary_window(chapters, volumes, chapter_summaries, start_order, end_order)
        if window is None:
            raise ValidationError("该区间缺少可参与聚合的章节摘要，需先生成满足条件的章节摘要。")
        key = _long_term_item_key(start_order, end_order)
        existing_item = existing_map.get(key)
        current_row = existing_long_term_by_range.get((start_order, end_order))
        is_ready_and_fresh = (
            current_row is not None
            and current_row.status == SUMMARY_STATUS_READY
            and not is_long_term_summary_stale(current_row, chapters, chapter_summaries, volumes)
        )
        if is_ready_and_fresh:
            if current_row is not None:
                summary_ids.append(current_row.id)
            if existing_item is not None:
                item_ids.append(existing_item.id)
            continue
        if current_row is not None and current_row.status == SUMMARY_STATUS_READY:
            row = current_row
        else:
            row = await create_or_update_long_term_summary(
                session,
                project_id,
                window.source_summaries,
                status=SUMMARY_STATUS_QUEUED,
                source_chapter_ids=window.chapter_ids,
                model_id=model_id,
            )
        if existing_item is not None:
            if row.status != SUMMARY_STATUS_READY:
                row.job_id = existing_item.id
                await chapter_summary_repo.update(session, row)
            item_ids.append(existing_item.id)
            summary_ids.append(row.id)
            await _publish_batch_item_queued_event(
                session,
                batch_job,
                item=existing_item,
                item_type=SUMMARY_BATCH_ITEM_TYPE_LONG_TERM,
                project_id=project_id,
                summary_id=row.id,
                start_order=start_order,
                end_order=end_order,
            )
            continue
        item = await _append_batch_item(
            session,
            batch_job_id=batch_job.id,
            order_index=order_index,
            item_key=key,
            item_type=SUMMARY_BATCH_ITEM_TYPE_LONG_TERM,
            payload={
                "project_id": project_id,
                "start_order": start_order,
                "end_order": end_order,
                "model_id": model_id,
                "model_policy": model_policy,
            },
        )
        order_index += 1
        if row.status != SUMMARY_STATUS_READY:
            row.job_id = item.id
            await chapter_summary_repo.update(session, row)
        item_ids.append(item.id)
        summary_ids.append(row.id)
        await _publish_batch_item_queued_event(
            session,
            batch_job,
            item=item,
            item_type=SUMMARY_BATCH_ITEM_TYPE_LONG_TERM,
            project_id=project_id,
            summary_id=row.id,
            start_order=start_order,
            end_order=end_order,
        )
    if created:
        return SummaryBatchAppendResult(batch_job.id, item_ids, [], summary_ids)
    return SummaryBatchAppendResult(batch_job.id, item_ids, [], summary_ids)


async def _auto_chapter_candidates(
    session: AsyncSession,
    project_id: str,
    anchor_chapter: Chapter | None = None,
) -> list[str]:
    summaries = await list_chapter_summaries(session, project_id)
    chapters = await chapter_repo.list_by_project(session, project_id)
    volumes = await volume_repo.list_by_project(session, project_id)
    eligible_chapters = [item for item in chapters if not is_chapter_summary_skipped(item)]
    has_ready_summary = any(summary.status == SUMMARY_STATUS_READY for summary in summaries)
    if not has_ready_summary and len(eligible_chapters) > AUTO_GENERATION_BLOCK_CHAPTER_THRESHOLD:
        return []
    summary_by_chapter_id = {summary.chapter_id: summary for summary in summaries}
    candidates: list[str] = []
    if anchor_chapter is not None:
        for chapter_group in _fixed_summary_windows(chapters, volumes, CHAPTER_SUMMARY_INTERVAL):
            if anchor_chapter.id not in {item.id for item in chapter_group}:
                continue
            for item in chapter_group:
                if is_chapter_summary_skipped(item):
                    continue
                existing = summary_by_chapter_id.get(item.id)
                if existing is None or existing.status not in {
                    SUMMARY_STATUS_READY,
                    SUMMARY_STATUS_QUEUED,
                    SUMMARY_STATUS_RUNNING,
                }:
                    candidates.append(item.id)
            return candidates
    for chapter_group in _fixed_summary_windows(chapters, volumes, CHAPTER_SUMMARY_INTERVAL):
        for item in chapter_group:
            if is_chapter_summary_skipped(item) or item.id in candidates:
                continue
            existing = summary_by_chapter_id.get(item.id)
            if existing is None or existing.status not in {
                SUMMARY_STATUS_READY,
                SUMMARY_STATUS_QUEUED,
                SUMMARY_STATUS_RUNNING,
            }:
                candidates.append(item.id)
    return candidates


async def maybe_enqueue_chapter_summary_for_new_chapter(
    session: AsyncSession,
    chapter: Chapter,
) -> SummaryBatchAppendResult | None:
    candidates = await _auto_chapter_candidates(session, chapter.project_id, anchor_chapter=chapter)
    if not candidates:
        return None
    return await append_chapter_summary_items(
        session,
        chapter.project_id,
        candidates,
    )


async def enqueue_long_term_summary_if_ready(
    session: AsyncSession,
    project_id: str,
    *,
    model_id: str | None = None,
    model_policy: str = "light_model",
    batch_job_id: str | None = None,
) -> SummaryBatchAppendResult | None:
    chapters = await chapter_repo.list_by_project(session, project_id)
    volumes = await volume_repo.list_by_project(session, project_id)
    chapter_summaries = await list_chapter_summaries(session, project_id)
    long_term_summaries = await list_long_term_summaries(session, project_id)
    windows = list_ready_unaggregated_long_term_windows(
        chapters,
        volumes,
        chapter_summaries,
        long_term_summaries,
    )
    if not windows:
        return None
    ranges = [(window.start_order, window.end_order) for window in windows]
    return await append_long_term_summary_items(
        session,
        project_id,
        ranges,
        model_id=model_id,
        model_policy=model_policy,
    )


async def enqueue_chapter_summary(
    session: AsyncSession,
    chapter_id: str,
    *,
    model_id: str | None = None,
    model_policy: str = "light_model",
) -> ChapterSummary:
    chapter = await chapter_repo.get_by_id(session, chapter_id)
    if chapter is None:
        raise NotFoundError(f"章节不存在: {chapter_id}")
    await append_chapter_summary_items(
        session,
        chapter.project_id,
        [chapter_id],
        model_id=model_id,
        model_policy=model_policy,
    )
    row = await chapter_summary_repo.get_by_chapter_id(session, chapter_id)
    if row is None:
        raise NotFoundError(f"章节摘要不存在: {chapter_id}")
    return row


async def enqueue_long_term_summary_range(
    session: AsyncSession,
    project_id: str,
    start_order: int,
    end_order: int,
    source: list[ChapterSummary],
    *,
    model_id: str | None = None,
    model_policy: str = "light_model",
) -> ChapterSummary:
    _ = source
    await append_long_term_summary_items(
        session,
        project_id,
        [(start_order, end_order)],
        model_id=model_id,
        model_policy=model_policy,
    )
    row = await chapter_summary_repo.get_long_term_by_range(
        session,
        project_id,
        start_order,
        end_order,
    )
    if row is None:
        raise NotFoundError("区间摘要不存在")
    return row


async def list_active_summary_jobs(
    session: AsyncSession,
    project_id: str,
    chapter_summaries: list[ChapterSummary],
    long_term_summaries: list[ChapterSummary],
) -> list[ActiveSummaryJob]:
    jobs = await job_service.list_jobs(
        session,
        subject_type="project",
        subject_id=project_id,
        statuses={
            JOB_STATUS_PENDING,
            JOB_STATUS_RUNNING,
        },
        job_types={JOB_TYPE_SUMMARY_BATCH},
        limit=500,
        offset=0,
    )
    if not jobs:
        jobs = await job_service.list_jobs(
            session,
            subject_type="project",
            subject_id=project_id,
            job_types={JOB_TYPE_SUMMARY_BATCH},
            limit=1,
            offset=0,
        )
    active_jobs: list[ActiveSummaryJob] = []

    for job in jobs:
        items = await job_service.list_job_items(session, job_id=job.id)
        chapter_by_job_id = {summary.job_id: summary for summary in chapter_summaries if summary.job_id}
        long_term_by_job_id = {
            summary.job_id: summary for summary in long_term_summaries if summary.job_id
        }
        for item in items:
            if item.status not in {JOB_STATUS_PENDING, JOB_STATUS_RUNNING}:
                continue
            payload = job_service.parse_json_object(item.payload_json)
            progress = job_service.parse_json_object(item.progress_json)
            error = job_service.parse_json_object(item.error_json)
            summary_id = None
            start_order = None
            end_order = None
            chapter_id = payload.get("chapter_id")
            if item.type == SUMMARY_BATCH_ITEM_TYPE_CHAPTER:
                summary = chapter_by_job_id.get(item.id)
                if summary is not None:
                    summary_id = summary.id
                    start_order = summary.start_order
                    end_order = summary.end_order
            elif item.type == SUMMARY_BATCH_ITEM_TYPE_LONG_TERM:
                summary = long_term_by_job_id.get(item.id)
                if summary is not None:
                    summary_id = summary.id
                    start_order = summary.start_order
                    end_order = summary.end_order
            active_jobs.append(
                ActiveSummaryJob(
                    job_id=item.id,
                    job_type=item.type,
                    status=item.status,
                    chapter_id=chapter_id if isinstance(chapter_id, str) else None,
                    summary_id=summary_id,
                    start_order=start_order,
                    end_order=end_order,
                    progress_current=int(progress.get("current") or 0),
                    progress_total=progress.get("total") if isinstance(progress.get("total"), int) else None,
                    progress_message=progress.get("message") if isinstance(progress.get("message"), str) else None,
                    error_message=error.get("message") if isinstance(error.get("message"), str) else None,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                )
            )
    return active_jobs
