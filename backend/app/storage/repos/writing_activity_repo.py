# -*- coding: utf-8 -*-
"""
Writing Activity Repository - 写作活动事件只读/写入查询。
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement
from sqlmodel import col

from app.storage.models.writing_activity_event import WritingActivityEvent


@dataclass(frozen=True)
class WritingActivityFilters:
    """写作活动筛选条件。"""

    project_id: str | None = None
    source: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    timezone: ZoneInfo = ZoneInfo("UTC")


@dataclass(frozen=True)
class WritingActivitySummaryRow:
    """写作活动事件汇总。"""

    active_days: int
    creative_chapters: int


@dataclass(frozen=True)
class WritingActivityTimeSeriesRow:
    """按日期聚合的写作活动行。"""

    date: str
    user_word_delta: int
    agent_word_delta: int
    import_word_delta: int


async def create(
    session: AsyncSession,
    event: WritingActivityEvent,
) -> WritingActivityEvent:
    """创建写作活动事件。"""
    session.add(event)
    await session.flush()
    await session.refresh(event)
    return event


async def get_activity_summary(
    session: AsyncSession,
    filters: WritingActivityFilters,
) -> WritingActivitySummaryRow:
    """获取写作活动事件汇总。"""
    rows = await list_events_for_aggregation(session, filters)
    creative_rows = [row for row in rows if row.source in {"user", "agent"}]
    dates = {_format_activity_date(row.created_at, filters.timezone) for row in creative_rows}
    chapter_ids = {row.chapter_id for row in creative_rows if row.chapter_id}
    return WritingActivitySummaryRow(
        active_days=len(dates),
        creative_chapters=len(chapter_ids),
    )


async def list_time_series(
    session: AsyncSession,
    filters: WritingActivityFilters,
) -> list[WritingActivityTimeSeriesRow]:
    """按日期聚合写作活动。"""
    rows = await list_events_for_aggregation(session, filters)
    grouped: dict[str, list[WritingActivityEvent]] = {}
    for row in rows:
        grouped.setdefault(_format_activity_date(row.created_at, filters.timezone), []).append(row)

    return [
        WritingActivityTimeSeriesRow(
            date=date,
            user_word_delta=sum(item.word_delta for item in items if item.source == "user"),
            agent_word_delta=sum(item.word_delta for item in items if item.source == "agent"),
            import_word_delta=sum(item.word_delta for item in items if item.source == "import"),
        )
        for date, items in sorted(grouped.items())
    ]


async def list_events_for_aggregation(
    session: AsyncSession,
    filters: WritingActivityFilters,
) -> list[WritingActivityEvent]:
    """获取用于写作统计聚合的事件。"""
    query = select(WritingActivityEvent).order_by(col(WritingActivityEvent.created_at).asc())
    conditions = _conditions(filters)
    if conditions:
        query = query.where(*conditions)
    result = await session.execute(query)
    return list(result.scalars().all())


def _conditions(filters: WritingActivityFilters) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if filters.project_id:
        conditions.append(col(WritingActivityEvent.project_id) == filters.project_id)
    if filters.source:
        conditions.append(col(WritingActivityEvent.source) == filters.source)
    if filters.start_at:
        conditions.append(col(WritingActivityEvent.created_at) >= filters.start_at)
    if filters.end_at:
        conditions.append(col(WritingActivityEvent.created_at) <= filters.end_at)
    return conditions


def _format_activity_date(value: datetime, timezone: ZoneInfo) -> str:
    """按用户时区返回写作活动所属日期。"""
    source = value if value.tzinfo else value.replace(tzinfo=UTC)
    return source.astimezone(timezone).strftime("%Y-%m-%d")
