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
    agent_nodes: list[str]
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
    agent_node: str | None = None,
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
        agent_node=agent_node,
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
    """获取仪表盘统计数据，不加载记录列表。"""
    metric_rows = await dashboard_repo.list_metric_rows(session, filters)
    return DashboardStatsResult(
        summary=_build_summary(metric_rows),
        model_time_series=_build_model_time_series(metric_rows),
        by_model=_build_breakdown(metric_rows, "model", limit=None),
        by_project=_build_breakdown(metric_rows, "project", limit=None),
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
    records = await dashboard_repo.list_records(
        session,
        filters,
        limit=page_size,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )
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
    return DashboardFilterOptionsResult(
        project_ids=await dashboard_repo.list_distinct_values(session, "project_id"),
        model_providers=await dashboard_repo.list_distinct_values(
            session, "model_provider"
        ),
        model_ids=await dashboard_repo.list_distinct_values(session, "model_id"),
        agent_nodes=await dashboard_repo.list_distinct_values(session, "agent_node"),
        statuses=await dashboard_repo.list_distinct_values(session, "status"),
        project_options=await dashboard_repo.list_project_filter_options(session),
        model_options=await dashboard_repo.list_model_filter_options(session),
    )


def _average(values: list[int]) -> float:
    if not values:
        return 0
    return sum(values) / len(values)


def _build_summary(
    rows: list[dashboard_repo.DashboardMetricRow],
) -> dashboard_repo.DashboardSummaryRow:
    latency_values = [row.latency_ms for row in rows if row.latency_ms is not None]
    first_token_values = [
        row.first_token_ms for row in rows if row.first_token_ms is not None
    ]
    return dashboard_repo.DashboardSummaryRow(
        calls_total=len(rows),
        success_total=sum(1 for row in rows if row.status == "success"),
        tokens_total=sum(row.tokens_total for row in rows),
        tokens_input_total=sum(row.tokens_input for row in rows),
        tokens_output_total=sum(row.tokens_output for row in rows),
        avg_latency_ms=_average(latency_values),
        avg_first_token_ms=_average(first_token_values),
    )


def _build_model_time_series(
    rows: list[dashboard_repo.DashboardMetricRow],
) -> list[dashboard_repo.ModelTimeSeriesRow]:
    grouped: dict[tuple[str, str, str], list[dashboard_repo.DashboardMetricRow]] = {}
    for row in rows:
        key, label = _get_breakdown_key(row, "model")
        grouped.setdefault((row.created_at.strftime("%Y-%m-%d"), key, label), []).append(row)

    return [
        dashboard_repo.ModelTimeSeriesRow(
            date=date,
            key=key,
            label=label,
            calls=len(items),
            tokens_total=sum(item.tokens_total for item in items),
            avg_latency_ms=_average(
                [item.latency_ms for item in items if item.latency_ms is not None]
            ),
        )
        for (date, key, label), items in sorted(grouped.items())
    ]


def _build_breakdown(
    rows: list[dashboard_repo.DashboardMetricRow],
    group_name: str,
    limit: int | None = 12,
) -> list[dashboard_repo.BreakdownRow]:
    grouped: dict[tuple[str, str], list[dashboard_repo.DashboardMetricRow]] = {}
    for row in rows:
        key, label = _get_breakdown_key(row, group_name)
        grouped.setdefault((key, label), []).append(row)

    items = [
        dashboard_repo.BreakdownRow(
            key=key,
            label=label,
            calls=len(group_rows),
            tokens_total=sum(item.tokens_total for item in group_rows),
        )
        for (key, label), group_rows in grouped.items()
    ]
    sorted_items = sorted(items, key=lambda item: item.calls, reverse=True)
    if limit is None:
        return sorted_items
    return sorted_items[:limit]


def _get_breakdown_key(
    row: dashboard_repo.DashboardMetricRow,
    group_name: str,
) -> tuple[str, str]:
    if group_name == "model":
        return row.model_id or "unknown", row.model_name or row.model_id or "unknown"
    if group_name == "project":
        return row.project_id, row.project_title or row.project_id
    return "unknown", "unknown"
