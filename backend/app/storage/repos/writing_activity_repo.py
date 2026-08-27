# -*- coding: utf-8 -*-
"""
Writing Activity Repository - 写作活动事件只读/写入查询。
"""

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, literal, select, union_all
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


@dataclass(frozen=True)
class WritingActivityMetricRow:
    """用于写作统计的轻量事件行。"""

    created_at: datetime
    source: str
    chapter_id: str | None
    word_delta: int


@dataclass(frozen=True)
class WritingActivityAggregates:
    """写作统计聚合结果。"""

    summary: WritingActivitySummaryRow
    time_series: list[WritingActivityTimeSeriesRow]


async def create(
    session: AsyncSession,
    event: WritingActivityEvent,
) -> WritingActivityEvent:
    """创建写作活动事件。"""
    session.add(event)
    await session.flush()
    await session.refresh(event)
    return event


async def get_aggregates(
    session: AsyncSession,
    filters: WritingActivityFilters,
) -> WritingActivityAggregates | None:
    """在 SQLite 中聚合写作统计，无法安全折叠时返回 None。"""
    timezone_modifier = _fixed_timezone_modifier(filters.timezone)
    if timezone_modifier is None:
        return None

    filtered_query = select(
        col(WritingActivityEvent.created_at),
        col(WritingActivityEvent.source),
        col(WritingActivityEvent.chapter_id),
        col(WritingActivityEvent.word_delta),
    )
    conditions = _conditions(filters)
    if conditions:
        filtered_query = filtered_query.where(*conditions)
    filtered = filtered_query.cte("writing_activity").prefix_with("MATERIALIZED")
    date_expression = func.strftime(
        "%Y-%m-%d",
        filtered.c.created_at,
        literal(timezone_modifier),
    )
    creative_condition = filtered.c.source.in_(["user", "agent"])
    summary_query = select(
        literal("summary").label("kind"),
        literal(None).label("date"),
        func.count(func.distinct(case((creative_condition, date_expression)))).label(
            "active_days"
        ),
        func.count(
            func.distinct(case((creative_condition, filtered.c.chapter_id)))
        ).label("creative_chapters"),
        literal(None).label("user_word_delta"),
        literal(None).label("agent_word_delta"),
        literal(None).label("import_word_delta"),
    ).select_from(filtered)
    time_series_query = select(
        literal("time_series").label("kind"),
        date_expression.label("date"),
        literal(None).label("active_days"),
        literal(None).label("creative_chapters"),
        func.coalesce(
            func.sum(
                case(
                    (filtered.c.source == "user", filtered.c.word_delta),
                    else_=0,
                )
            ),
            0,
        ).label("user_word_delta"),
        func.coalesce(
            func.sum(
                case(
                    (filtered.c.source == "agent", filtered.c.word_delta),
                    else_=0,
                )
            ),
            0,
        ).label("agent_word_delta"),
        func.coalesce(
            func.sum(
                case(
                    (filtered.c.source == "import", filtered.c.word_delta),
                    else_=0,
                )
            ),
            0,
        ).label("import_word_delta"),
    ).select_from(filtered).group_by(date_expression)
    result = await session.execute(union_all(summary_query, time_series_query))
    summary = WritingActivitySummaryRow(active_days=0, creative_chapters=0)
    time_series: list[WritingActivityTimeSeriesRow] = []
    for row in result.all():
        if row.kind == "summary":
            summary = WritingActivitySummaryRow(
                active_days=int(row.active_days or 0),
                creative_chapters=int(row.creative_chapters or 0),
            )
        elif row.kind == "time_series":
            time_series.append(
                WritingActivityTimeSeriesRow(
                    date=row.date,
                    user_word_delta=int(row.user_word_delta or 0),
                    agent_word_delta=int(row.agent_word_delta or 0),
                    import_word_delta=int(row.import_word_delta or 0),
                )
            )
    time_series.sort(key=lambda item: item.date)
    return WritingActivityAggregates(summary=summary, time_series=time_series)


async def list_metric_rows(
    session: AsyncSession,
    filters: WritingActivityFilters,
) -> list[WritingActivityMetricRow]:
    """获取用于写作统计的轻量事件字段。"""
    query = select(
        col(WritingActivityEvent.created_at),
        col(WritingActivityEvent.source),
        col(WritingActivityEvent.chapter_id),
        col(WritingActivityEvent.word_delta),
    ).order_by(col(WritingActivityEvent.created_at).asc())
    conditions = _conditions(filters)
    if conditions:
        query = query.where(*conditions)
    result = await session.execute(query)
    return [
        WritingActivityMetricRow(
            created_at=row.created_at,
            source=row.source,
            chapter_id=row.chapter_id,
            word_delta=row.word_delta or 0,
        )
        for row in result.all()
    ]


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


def _fixed_timezone_modifier(timezone: ZoneInfo) -> str | None:
    """返回全年稳定时区的 SQLite 时间修饰符。"""
    sample_dates = (
        datetime(2024, 1, 1, tzinfo=timezone),
        datetime(2024, 7, 1, tzinfo=timezone),
    )
    offsets = {value.utcoffset() for value in sample_dates}
    if len(offsets) != 1:
        return None
    offset = next(iter(offsets))
    if offset is None:
        return "+00:00"
    total_seconds = int(offset.total_seconds())
    sign = "+" if total_seconds >= 0 else "-"
    hours, remainder = divmod(abs(total_seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    if seconds:
        return f"{sign}{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{sign}{hours:02d}:{minutes:02d}"
