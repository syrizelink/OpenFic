# -*- coding: utf-8 -*-
"""
Dashboard Service - LLM API 仪表盘查询编排。
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.repos import dashboard_repo


@dataclass(frozen=True)
class DashboardRecordPage:
    """分页记录结果。"""

    items: list[dashboard_repo.DashboardRecordRow]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True)
class DashboardFilterOptionsResult:
    """筛选选项结果。"""

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
    """仪表盘记录查询结果。"""

    options: DashboardFilterOptionsResult
    records: DashboardRecordPage


@dataclass(frozen=True)
class DashboardStatsResult:
    """仪表盘统计查询结果。"""

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
    """构建仪表盘筛选条件。"""
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
    """获取仪表盘统计数据，由数据库完成聚合。"""
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
    """获取仪表盘调用记录，不加载统计图表数据。"""
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
    """获取单条调用记录的输入提示词。"""
    return await dashboard_repo.get_record_prompt(session, record_id)


async def get_filter_options(session: AsyncSession) -> DashboardFilterOptionsResult:
    """获取全局筛选选项。"""
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
