# -*- coding: utf-8 -*-
"""Repository helpers for structured chapter summaries."""

from datetime import UTC, datetime

from sqlalchemy import and_, delete as sql_delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.chapter_summary import ChapterSummary

SUMMARY_TYPE_CHAPTER = "chapter"
SUMMARY_TYPE_LONG_TERM = "long_term"
SUMMARY_STATUS_NOT_GENERATED = "not_generated"
SUMMARY_STATUS_QUEUED = "queued"
SUMMARY_STATUS_RUNNING = "running"
SUMMARY_STATUS_READY = "ready"
SUMMARY_STATUS_FAILED = "failed"
ACTIVE_STATUSES = {SUMMARY_STATUS_QUEUED, SUMMARY_STATUS_RUNNING}


async def create(session: AsyncSession, summary: ChapterSummary) -> ChapterSummary:
    session.add(summary)
    await session.flush()
    await session.refresh(summary)
    return summary


async def get_by_id(session: AsyncSession, summary_id: str) -> ChapterSummary | None:
    result = await session.execute(
        select(ChapterSummary).where(col(ChapterSummary.id) == summary_id)
    )
    return result.scalar_one_or_none()


async def update(session: AsyncSession, summary: ChapterSummary) -> ChapterSummary:
    summary.updated_at = datetime.now(UTC)
    session.add(summary)
    await session.flush()
    await session.refresh(summary)
    return summary


async def delete(session: AsyncSession, summary: ChapterSummary) -> None:
    await session.delete(summary)
    await session.flush()


async def delete_by_id(session: AsyncSession, summary_id: str) -> bool:
    result = await session.execute(
        sql_delete(ChapterSummary).where(col(ChapterSummary.id) == summary_id)
    )
    await session.flush()
    return result.rowcount > 0  # type: ignore[attr-defined]


async def get_by_chapter_id(
    session: AsyncSession, chapter_id: str
) -> ChapterSummary | None:
    result = await session.execute(
        select(ChapterSummary).where(
            and_(
                col(ChapterSummary.summary_type) == SUMMARY_TYPE_CHAPTER,
                col(ChapterSummary.chapter_id) == chapter_id,
            )
        )
    )
    return result.scalar_one_or_none()


async def get_long_term_by_range(
    session: AsyncSession, project_id: str, start_order: int, end_order: int
) -> ChapterSummary | None:
    result = await session.execute(
        select(ChapterSummary).where(
            and_(
                col(ChapterSummary.summary_type) == SUMMARY_TYPE_LONG_TERM,
                col(ChapterSummary.project_id) == project_id,
                col(ChapterSummary.start_order) == start_order,
                col(ChapterSummary.end_order) == end_order,
            )
        )
    )
    return result.scalar_one_or_none()


async def list_chapter_summaries_by_project(
    session: AsyncSession, project_id: str
) -> list[ChapterSummary]:
    result = await session.execute(
        select(ChapterSummary)
        .where(
            and_(
                col(ChapterSummary.summary_type) == SUMMARY_TYPE_CHAPTER,
                col(ChapterSummary.project_id) == project_id,
            )
        )
        .order_by(col(ChapterSummary.chapter_order).asc())
    )
    return list(result.scalars().all())


async def count_chapter_summaries_by_project(
    session: AsyncSession, project_id: str, *, volume_id: str | None = None
) -> int:
    conditions = [
        col(ChapterSummary.summary_type) == SUMMARY_TYPE_CHAPTER,
        col(ChapterSummary.project_id) == project_id,
    ]
    if volume_id is not None:
        conditions.append(col(ChapterSummary.volume_id) == volume_id)
    result = await session.execute(
        select(func.count())
        .select_from(ChapterSummary)
        .where(and_(*conditions))
    )
    return int(result.scalar_one())


async def list_chapter_summaries_by_project_page(
    session: AsyncSession,
    project_id: str,
    *,
    offset: int,
    limit: int,
    volume_id: str | None = None,
) -> list[ChapterSummary]:
    conditions = [
        col(ChapterSummary.summary_type) == SUMMARY_TYPE_CHAPTER,
        col(ChapterSummary.project_id) == project_id,
    ]
    if volume_id is not None:
        conditions.append(col(ChapterSummary.volume_id) == volume_id)
    result = await session.execute(
        select(ChapterSummary)
        .where(and_(*conditions))
        .order_by(col(ChapterSummary.chapter_order).asc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def list_chapter_summaries_by_chapter_ids(
    session: AsyncSession, chapter_ids: list[str], *, ready_only: bool = False
) -> list[ChapterSummary]:
    if not chapter_ids:
        return []
    query = select(ChapterSummary).where(
        and_(
            col(ChapterSummary.summary_type) == SUMMARY_TYPE_CHAPTER,
            col(ChapterSummary.chapter_id).in_(chapter_ids),
        )
    )
    if ready_only:
        query = query.where(col(ChapterSummary.status) == SUMMARY_STATUS_READY)
    result = await session.execute(query)
    return list(result.scalars().all())


async def list_long_term_summaries_by_project(
    session: AsyncSession, project_id: str, *, ready_only: bool = False
) -> list[ChapterSummary]:
    query = (
        select(ChapterSummary)
        .where(
            and_(
                col(ChapterSummary.summary_type) == SUMMARY_TYPE_LONG_TERM,
                col(ChapterSummary.project_id) == project_id,
            )
        )
        .order_by(col(ChapterSummary.start_order).desc())
    )
    if ready_only:
        query = query.where(col(ChapterSummary.status) == SUMMARY_STATUS_READY)
    result = await session.execute(query)
    return list(result.scalars().all())


async def count_long_term_summaries_by_project(
    session: AsyncSession, project_id: str
) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(ChapterSummary)
        .where(
            and_(
                col(ChapterSummary.summary_type) == SUMMARY_TYPE_LONG_TERM,
                col(ChapterSummary.project_id) == project_id,
            )
        )
    )
    return int(result.scalar_one())


async def list_long_term_summaries_by_project_page(
    session: AsyncSession, project_id: str, *, offset: int, limit: int
) -> list[ChapterSummary]:
    result = await session.execute(
        select(ChapterSummary)
        .where(
            and_(
                col(ChapterSummary.summary_type) == SUMMARY_TYPE_LONG_TERM,
                col(ChapterSummary.project_id) == project_id,
            )
        )
        .order_by(col(ChapterSummary.start_order).desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def list_latest_long_term_summaries_by_ranges(
    session: AsyncSession, project_id: str, ranges: list[tuple[int, int]]
) -> list[ChapterSummary]:
    if not ranges:
        return []

    result = await session.execute(
        select(ChapterSummary)
        .where(
            and_(
                col(ChapterSummary.summary_type) == SUMMARY_TYPE_LONG_TERM,
                col(ChapterSummary.project_id) == project_id,
            )
        )
        .order_by(
            col(ChapterSummary.start_order).desc(),
            col(ChapterSummary.updated_at).desc(),
        )
    )
    target_ranges = set(ranges)
    latest_by_range: dict[tuple[int, int], ChapterSummary] = {}
    for summary in result.scalars().all():
        if summary.start_order is None or summary.end_order is None:
            continue
        key = (summary.start_order, summary.end_order)
        if key not in target_ranges or key in latest_by_range:
            continue
        latest_by_range[key] = summary
        if len(latest_by_range) == len(target_ranges):
            break
    return list(latest_by_range.values())


async def list_long_term_summaries_before_order(
    session: AsyncSession, project_id: str, before_order: int, *, ready_only: bool = True
) -> list[ChapterSummary]:
    query = (
        select(ChapterSummary)
        .where(
            and_(
                col(ChapterSummary.summary_type) == SUMMARY_TYPE_LONG_TERM,
                col(ChapterSummary.project_id) == project_id,
                col(ChapterSummary.end_order) < before_order,
            )
        )
        .order_by(col(ChapterSummary.start_order).desc())
    )
    if ready_only:
        query = query.where(col(ChapterSummary.status) == SUMMARY_STATUS_READY)
    result = await session.execute(query)
    return list(result.scalars().all())


async def delete_by_project(session: AsyncSession, project_id: str) -> None:
    await session.execute(
        sql_delete(ChapterSummary).where(col(ChapterSummary.project_id) == project_id)
    )
    await session.flush()


async def delete_by_chapter_id(session: AsyncSession, chapter_id: str) -> None:
    await session.execute(
        sql_delete(ChapterSummary).where(
            and_(
                col(ChapterSummary.summary_type) == SUMMARY_TYPE_CHAPTER,
                col(ChapterSummary.chapter_id) == chapter_id,
            )
        )
    )
    await session.flush()


async def delete_by_chapter_ids(session: AsyncSession, chapter_ids: list[str]) -> None:
    if not chapter_ids:
        return
    await session.execute(
        sql_delete(ChapterSummary).where(
            and_(
                col(ChapterSummary.summary_type) == SUMMARY_TYPE_CHAPTER,
                col(ChapterSummary.chapter_id).in_(chapter_ids),
            )
        )
    )
    await session.flush()


async def delete_all_chapter_summaries_by_project(
    session: AsyncSession, project_id: str
) -> None:
    await session.execute(
        sql_delete(ChapterSummary).where(
            and_(
                col(ChapterSummary.summary_type) == SUMMARY_TYPE_CHAPTER,
                col(ChapterSummary.project_id) == project_id,
            )
        )
    )
    await session.flush()


async def delete_long_term_summaries_by_ranges(
    session: AsyncSession, project_id: str, ranges: list[tuple[int, int]]
) -> None:
    if not ranges:
        return
    range_conditions = [
        and_(
            col(ChapterSummary.start_order) == start_order,
            col(ChapterSummary.end_order) == end_order,
        )
        for start_order, end_order in ranges
    ]

    await session.execute(
        sql_delete(ChapterSummary).where(
            and_(
                col(ChapterSummary.summary_type) == SUMMARY_TYPE_LONG_TERM,
                col(ChapterSummary.project_id) == project_id,
                or_(*range_conditions),
            )
        )
    )
    await session.flush()


async def delete_all_long_term_summaries_by_project(
    session: AsyncSession, project_id: str
) -> None:
    await session.execute(
        sql_delete(ChapterSummary).where(
            and_(
                col(ChapterSummary.summary_type) == SUMMARY_TYPE_LONG_TERM,
                col(ChapterSummary.project_id) == project_id,
            )
        )
    )
    await session.flush()
