# -*- coding: utf-8 -*-
"""
Dashboard Service - orkestrasi kueri dasbor LLM API.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.repos import dashboard_repo


@dataclass(frozen=True)
class DashboardRecordPage:
    """Hasil catatan terpaginasi."""

    items: list[dashboard_repo.DashboardRecordRow]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True)
class DashboardFilterOptionsResult:
    """Hasil opsi filter."""

    project_ids: list[str]
    model_providers: list[str]
    model_ids: list[str]
    categories: list[str]
    operations: list[str]
    statuses: list[str]
    project_options: list[dashboard_repo.FilterOptionRow]
    model_options: list[dashboard_repo.FilterOptionRow]


@dataclass(frozen=True)
class DashboardRecordsResult:
    """Hasil kueri catatan dasbor."""

    options: DashboardFilterOptionsResult
    records: DashboardRecordPage


@dataclass(frozen=True)
class DashboardStatsResult:
    """Hasil kueri statistik dasbor."""

    summary: dashboard_repo.DashboardSummaryRow
    model_time_series: list[dashboard_repo.ModelTimeSeriesRow]
    by_model: list[dashboard_repo.BreakdownRow]
    by_project: list[dashboard_repo.BreakdownRow]
    options: DashboardFilterOptionsResult


def build_filters(
    project_id: str | None = None,
    model_provider: str | None = None,
    model_id: str | None = None,
    category: str | None = None,
    operation: str | None = None,
    status: str | None = None,
    task_id: str | None = None,
    session_id: str | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    search: str | None = None,
) -> dashboard_repo.DashboardFilters:
    """Membangun kriteria filter dasbor."""
    return dashboard_repo.DashboardFilters(
        project_id=project_id,
        model_provider=model_provider,
        model_id=model_id,
        category=category,
        operation=operation,
        status=status,
        task_id=task_id,
        session_id=session_id,
        start_at=start_at,
        end_at=end_at,
        search=search.strip() if search else None,
    )


async def get_stats_dashboard(
    session: AsyncSession,
    filters: dashboard_repo.DashboardFilters,
) -> DashboardStatsResult:
    """Mengambil data statistik dasbor, agregasi dikerjakan basis data."""
    stats = await dashboard_repo.get_stats(session, filters)
    return DashboardStatsResult(
        summary=stats.summary,
        model_time_series=stats.model_time_series,
        by_model=stats.by_model,
        by_project=stats.by_project,
        options=await get_filter_options(session),
    )


async def get_records_dashboard(
    session: AsyncSession,
    filters: dashboard_repo.DashboardFilters,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str,
) -> DashboardRecordsResult:
    """Mengambil catatan panggilan dasbor, tanpa memuat data grafik statistik."""
    offset = (page - 1) * page_size
    records, total = await dashboard_repo.list_records(
        session,
        filters,
        limit=page_size,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    if total is None:
        total = await dashboard_repo.count_records(session, filters)
    return DashboardRecordsResult(
        options=await get_filter_options(session),
        records=DashboardRecordPage(
            items=records,
            total=total,
            page=page,
            page_size=page_size,
        ),
    )


async def get_record_prompt(
    session: AsyncSession,
    record_id: str,
) -> dashboard_repo.DashboardRecordPromptRow | None:
    """Mengambil prompt masukan dari satu catatan panggilan."""
    return await dashboard_repo.get_record_prompt(session, record_id)


async def get_filter_options(session: AsyncSession) -> DashboardFilterOptionsResult:
    """Mengambil opsi filter global."""
    options = await dashboard_repo.get_filter_options(session)
    return DashboardFilterOptionsResult(
        project_ids=options.project_ids,
        model_providers=options.model_providers,
        model_ids=options.model_ids,
        categories=options.categories,
        operations=options.operations,
        statuses=options.statuses,
        project_options=options.project_options,
        model_options=options.model_options,
    )
