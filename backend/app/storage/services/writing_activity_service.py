# -*- coding: utf-8 -*-
"""
Writing Activity Service - pengumpulan dan statistik aktivitas menulis.
"""

from dataclasses import dataclass
from collections import defaultdict
from datetime import UTC, datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models.writing_activity_event import WritingActivityEvent
from app.storage.repos import writing_activity_repo

WritingActivitySource = Literal["user", "agent", "import"]
WritingActivityOperation = Literal[
    "create",
    "update",
    "delete",
    "import",
    "move_to_volume",
]


@dataclass(frozen=True)
class WritingDashboardResult:
    """Hasil statistik menulis."""

    summary: writing_activity_repo.WritingActivitySummaryRow
    time_series: list[writing_activity_repo.WritingActivityTimeSeriesRow]


def build_filters(
    project_id: str | None = None,
    source: str | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    timezone: str | None = None,
) -> writing_activity_repo.WritingActivityFilters:
    """Membangun kriteria filter statistik menulis."""
    parsed_timezone = _parse_timezone(timezone)
    return writing_activity_repo.WritingActivityFilters(
        project_id=project_id,
        source=source,
        start_at=_to_utc_datetime(start_at, parsed_timezone),
        end_at=_to_utc_datetime(end_at, parsed_timezone),
        timezone=parsed_timezone,
    )


def _parse_timezone(value: str | None) -> ZoneInfo:
    """Mem-parsing zona waktu klien, nilai tidak valid kembali ke UTC."""
    if not value:
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _to_utc_datetime(value: datetime | None, timezone: ZoneInfo) -> datetime | None:
    """Mengubah batas waktu lokal klien menjadi UTC."""
    if value is None:
        return None
    source = value if value.tzinfo else value.replace(tzinfo=timezone)
    return source.astimezone(UTC)


async def record_activity(
    session: AsyncSession,
    *,
    project_id: str,
    chapter_id: str | None,
    chapter_title: str | None,
    source: WritingActivitySource,
    operation: WritingActivityOperation,
    old_word_count: int | None,
    new_word_count: int | None,
    revision_id: str | None = None,
    task_id: str | None = None,
    agent_session_id: str | None = None,
) -> WritingActivityEvent | None:
    """Mencatat satu peristiwa perubahan jumlah kata isi bab."""
    old_count = old_word_count or 0
    new_count = new_word_count or 0
    if old_count == new_count and operation == "update":
        return None

    event = WritingActivityEvent(
        project_id=project_id,
        chapter_id=chapter_id,
        chapter_title=chapter_title,
        source=source,
        operation=operation,
        old_word_count=old_count,
        new_word_count=new_count,
        word_delta=new_count - old_count,
        revision_id=revision_id,
        task_id=task_id,
        agent_session_id=agent_session_id,
    )
    return await writing_activity_repo.create(session, event)


async def get_dashboard(
    session: AsyncSession,
    filters: writing_activity_repo.WritingActivityFilters,
) -> WritingDashboardResult:
    """Mengambil data dasbor statistik menulis."""
    aggregates = await writing_activity_repo.get_aggregates(session, filters)
    if aggregates is not None:
        return WritingDashboardResult(
            summary=aggregates.summary,
            time_series=aggregates.time_series,
        )
    rows = await writing_activity_repo.list_metric_rows(session, filters)
    return _build_dashboard_from_rows(rows, filters.timezone)


def _build_dashboard_from_rows(
    rows: list[writing_activity_repo.WritingActivityMetricRow],
    timezone: ZoneInfo,
) -> WritingDashboardResult:
    """Mempertahankan agregasi Python yang presisi untuk wilayah dengan pergantian zona waktu."""
    active_dates: set[str] = set()
    chapter_ids: set[str] = set()
    grouped: dict[str, dict[str, int]] = defaultdict(
        lambda: {"user": 0, "agent": 0, "import": 0}
    )
    for row in rows:
        date = _format_activity_date(row.created_at, timezone)
        if row.source in {"user", "agent"}:
            active_dates.add(date)
            if row.chapter_id:
                chapter_ids.add(row.chapter_id)
        if row.source in grouped[date]:
            grouped[date][row.source] += row.word_delta

    return WritingDashboardResult(
        summary=writing_activity_repo.WritingActivitySummaryRow(
            active_days=len(active_dates),
            creative_chapters=len(chapter_ids),
        ),
        time_series=[
            writing_activity_repo.WritingActivityTimeSeriesRow(
                date=date,
                user_word_delta=values["user"],
                agent_word_delta=values["agent"],
                import_word_delta=values["import"],
            )
            for date, values in sorted(grouped.items())
        ],
    )


def _format_activity_date(value: datetime, timezone: ZoneInfo) -> str:
    """Mengembalikan tanggal aktivitas menulis menurut zona waktu pengguna."""
    source = value if value.tzinfo else value.replace(tzinfo=UTC)
    return source.astimezone(timezone).strftime("%Y-%m-%d")
