# -*- coding: utf-8 -*-
"""
Dashboard Repository - LLM API 仪表盘只读查询。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Float, Integer, String, case, cast, func, literal, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement
from sqlmodel import col

from app.storage.models.llm_audit_log import LLMAuditLog
from app.storage.models.project import Project


@dataclass(frozen=True)
class DashboardFilters:
    """仪表盘筛选条件。"""

    project_id: str | None = None
    model_provider: str | None = None
    model_id: str | None = None
    category: str | None = None
    operation: str | None = None
    status: str | None = None
    task_id: str | None = None
    session_id: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    search: str | None = None


@dataclass(frozen=True)
class DashboardSummaryRow:
    """总览聚合行。"""

    calls_total: int
    success_total: int
    tokens_total: int
    tokens_input_total: int
    tokens_output_total: int
    avg_latency_ms: float
    avg_first_token_ms: float


@dataclass(frozen=True)
class ModelTimeSeriesRow:
    """按日期和模型聚合的趋势行。"""

    date: str
    key: str
    label: str
    calls: int
    tokens_total: int
    avg_latency_ms: float


@dataclass(frozen=True)
class BreakdownRow:
    """分组聚合行。"""

    key: str
    label: str
    calls: int
    tokens_total: int


@dataclass(frozen=True)
class DashboardRecordRow:
    """用于记录列表展示的轻量审计行。"""

    id: str
    created_at: datetime
    task_id: str | None
    session_id: str | None
    project_id: str
    project_title: str | None
    chapter_id: str | None
    revision_id: str | None
    category: str
    operation: str
    model_id: str
    model_provider: str | None
    model_name: str | None
    tokens_input: int
    tokens_output: int
    tokens_total: int
    token_cache: int
    latency_ms: int | None
    first_token_ms: int | None
    status: str
    error_type: str | None
    error_message: str | None
    error_status_code: int | None
    tool_calls_count: int
    has_request_messages: bool
    tool_references: str | None
    response_content: str | None
    response_tool_calls: str | None


@dataclass(frozen=True)
class DashboardRecordPromptRow:
    """调用记录输入提示词详情。"""

    id: str
    request_messages: str | None


@dataclass(frozen=True)
class FilterOptionRow:
    """筛选选项显示项。"""

    value: str
    label: str


@dataclass(frozen=True)
class DashboardFilterOptionsRow:
    """仪表盘筛选选项查询结果。"""

    project_ids: list[str]
    model_providers: list[str]
    model_ids: list[str]
    categories: list[str]
    operations: list[str]
    statuses: list[str]
    project_options: list[FilterOptionRow]
    model_options: list[FilterOptionRow]


@dataclass(frozen=True)
class DashboardStatsRows:
    """仪表盘统计聚合结果。"""

    summary: DashboardSummaryRow
    model_time_series: list[ModelTimeSeriesRow]
    by_model: list[BreakdownRow]
    by_project: list[BreakdownRow]


SORT_COLUMNS = {
    "created_at": LLMAuditLog.created_at,
    "tokens_input": LLMAuditLog.tokens_input,
    "tokens_output": LLMAuditLog.tokens_output,
    "tokens_total": LLMAuditLog.tokens_total,
    "latency_ms": LLMAuditLog.latency_ms,
    "first_token_ms": LLMAuditLog.first_token_ms,
    "tool_calls_count": LLMAuditLog.tool_calls_count,
}


def _conditions(filters: DashboardFilters) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if filters.project_id:
        conditions.append(col(LLMAuditLog.project_id) == filters.project_id)
    if filters.model_provider:
        conditions.append(col(LLMAuditLog.model_provider) == filters.model_provider)
    if filters.model_id:
        conditions.append(col(LLMAuditLog.model_id) == filters.model_id)
    if filters.category:
        conditions.append(col(LLMAuditLog.category) == filters.category)
    if filters.operation:
        conditions.append(col(LLMAuditLog.operation) == filters.operation)
    if filters.status:
        conditions.append(col(LLMAuditLog.status) == filters.status)
    if filters.task_id:
        conditions.append(col(LLMAuditLog.task_id) == filters.task_id)
    if filters.session_id:
        conditions.append(col(LLMAuditLog.session_id) == filters.session_id)
    if filters.start_at:
        conditions.append(col(LLMAuditLog.created_at) >= filters.start_at)
    if filters.end_at:
        conditions.append(col(LLMAuditLog.created_at) <= filters.end_at)
    if filters.search:
        like_value = f"%{filters.search}%"
        conditions.append(
            or_(
                col(LLMAuditLog.id).contains(filters.search),
                col(LLMAuditLog.model_id).contains(filters.search),
                col(LLMAuditLog.model_name).like(like_value),
                col(LLMAuditLog.category).like(like_value),
                col(LLMAuditLog.operation).like(like_value),
                col(LLMAuditLog.task_id).like(like_value),
                col(LLMAuditLog.session_id).like(like_value),
                col(LLMAuditLog.error_message).like(like_value),
            )
        )
    return conditions


def _apply_filters(query, filters: DashboardFilters):
    conditions = _conditions(filters)
    if conditions:
        return query.where(*conditions)
    return query


def _null_value(name: str, value_type: Any):
    return literal(None, type_=value_type).label(name)


async def get_stats(
    session: AsyncSession,
    filters: DashboardFilters,
) -> DashboardStatsRows:
    """通过一次 SQL 查询完成仪表盘统计聚合。"""
    filtered_query = select(
        col(LLMAuditLog.id),
        col(LLMAuditLog.created_at),
        col(LLMAuditLog.project_id),
        col(Project.title).label("project_title"),
        col(LLMAuditLog.model_id),
        col(LLMAuditLog.model_name),
        col(LLMAuditLog.tokens_input),
        col(LLMAuditLog.tokens_output),
        col(LLMAuditLog.tokens_total),
        col(LLMAuditLog.latency_ms),
        col(LLMAuditLog.first_token_ms),
        col(LLMAuditLog.status),
    ).outerjoin(Project, col(Project.id) == col(LLMAuditLog.project_id))
    filtered = (
        _apply_filters(filtered_query, filters)
        .cte("dashboard_metrics")
        .prefix_with("MATERIALIZED")
    )
    date_expression = func.strftime("%Y-%m-%d", filtered.c.created_at)
    model_id_expression = func.nullif(filtered.c.model_id, "")
    model_key_expression = func.coalesce(model_id_expression, literal("unknown"))
    model_label_expression = func.coalesce(
        func.nullif(filtered.c.model_name, ""),
        model_id_expression,
        literal("unknown"),
    )
    project_id_expression = func.nullif(filtered.c.project_id, "")
    project_key_expression = func.coalesce(project_id_expression, literal("unknown"))
    project_label_expression = func.coalesce(
        func.nullif(filtered.c.project_title, ""),
        project_id_expression,
        literal("unknown"),
    )
    summary_query = select(
        literal("summary").label("kind"),
        _null_value("date", String()),
        _null_value("key", String()),
        _null_value("label", String()),
        func.count(filtered.c.id).label("calls"),
        func.coalesce(func.sum(filtered.c.tokens_total), 0).label("tokens_total"),
        func.coalesce(func.avg(filtered.c.latency_ms), 0).label("avg_latency_ms"),
        func.coalesce(func.avg(filtered.c.first_token_ms), 0).label("avg_first_token_ms"),
        func.coalesce(func.sum(filtered.c.tokens_input), 0).label("tokens_input_total"),
        func.coalesce(func.sum(filtered.c.tokens_output), 0).label("tokens_output_total"),
        func.coalesce(
            func.sum(case((filtered.c.status == "success", 1), else_=0)),
            0,
        ).label("success_total"),
    ).select_from(filtered)
    model_time_series_query = select(
        literal("model_time_series").label("kind"),
        date_expression.label("date"),
        model_key_expression.label("key"),
        model_label_expression.label("label"),
        func.count(filtered.c.id).label("calls"),
        func.coalesce(func.sum(filtered.c.tokens_total), 0).label("tokens_total"),
        func.coalesce(func.avg(filtered.c.latency_ms), 0).label("avg_latency_ms"),
        _null_value("avg_first_token_ms", Float()),
        _null_value("tokens_input_total", Integer()),
        _null_value("tokens_output_total", Integer()),
        _null_value("success_total", Integer()),
    ).select_from(filtered).group_by(
        date_expression,
        model_key_expression,
        model_label_expression,
    )
    model_breakdown_query = select(
        literal("model_breakdown").label("kind"),
        _null_value("date", String()),
        model_key_expression.label("key"),
        model_label_expression.label("label"),
        func.count(filtered.c.id).label("calls"),
        func.coalesce(func.sum(filtered.c.tokens_total), 0).label("tokens_total"),
        _null_value("avg_latency_ms", Float()),
        _null_value("avg_first_token_ms", Float()),
        _null_value("tokens_input_total", Integer()),
        _null_value("tokens_output_total", Integer()),
        _null_value("success_total", Integer()),
    ).select_from(filtered).group_by(model_key_expression, model_label_expression)
    project_breakdown_query = select(
        literal("project_breakdown").label("kind"),
        _null_value("date", String()),
        project_key_expression.label("key"),
        project_label_expression.label("label"),
        func.count(filtered.c.id).label("calls"),
        func.coalesce(func.sum(filtered.c.tokens_total), 0).label("tokens_total"),
        _null_value("avg_latency_ms", Float()),
        _null_value("avg_first_token_ms", Float()),
        _null_value("tokens_input_total", Integer()),
        _null_value("tokens_output_total", Integer()),
        _null_value("success_total", Integer()),
    ).select_from(filtered).group_by(project_key_expression, project_label_expression)
    result = await session.execute(
        union_all(
            summary_query,
            model_time_series_query,
            model_breakdown_query,
            project_breakdown_query,
        )
    )
    summary: DashboardSummaryRow | None = None
    model_time_series: list[ModelTimeSeriesRow] = []
    by_model: list[BreakdownRow] = []
    by_project: list[BreakdownRow] = []
    for row in result.all():
        if row.kind == "summary":
            summary = DashboardSummaryRow(
                calls_total=int(row.calls or 0),
                success_total=int(row.success_total or 0),
                tokens_total=int(row.tokens_total or 0),
                tokens_input_total=int(row.tokens_input_total or 0),
                tokens_output_total=int(row.tokens_output_total or 0),
                avg_latency_ms=float(row.avg_latency_ms or 0),
                avg_first_token_ms=float(row.avg_first_token_ms or 0),
            )
        elif row.kind == "model_time_series":
            model_time_series.append(
                ModelTimeSeriesRow(
                    date=row.date,
                    key=row.key,
                    label=row.label,
                    calls=int(row.calls or 0),
                    tokens_total=int(row.tokens_total or 0),
                    avg_latency_ms=float(row.avg_latency_ms or 0),
                )
            )
        elif row.kind == "model_breakdown":
            by_model.append(
                BreakdownRow(
                    key=row.key,
                    label=row.label,
                    calls=int(row.calls or 0),
                    tokens_total=int(row.tokens_total or 0),
                )
            )
        elif row.kind == "project_breakdown":
            by_project.append(
                BreakdownRow(
                    key=row.key,
                    label=row.label,
                    calls=int(row.calls or 0),
                    tokens_total=int(row.tokens_total or 0),
                )
            )

    if summary is None:
        summary = DashboardSummaryRow(0, 0, 0, 0, 0, 0, 0)
    model_time_series.sort(key=lambda item: (item.date, item.key, item.label))
    by_model.sort(key=lambda item: item.calls, reverse=True)
    by_project.sort(key=lambda item: item.calls, reverse=True)
    return DashboardStatsRows(summary, model_time_series, by_model, by_project)


async def count_records(session: AsyncSession, filters: DashboardFilters) -> int:
    """统计筛选后的记录数。"""
    query = select(func.count(col(LLMAuditLog.id)))
    return (await session.execute(_apply_filters(query, filters))).scalar_one()


async def list_records(
    session: AsyncSession,
    filters: DashboardFilters,
    limit: int,
    offset: int,
    sort_by: str,
    sort_order: str,
) -> tuple[list[DashboardRecordRow], int | None]:
    """获取筛选后的审计记录。"""
    sort_column = SORT_COLUMNS.get(sort_by, LLMAuditLog.created_at)
    order_expression = (
        col(sort_column).asc() if sort_order == "asc" else col(sort_column).desc()
    )
    page_query = select(
        col(LLMAuditLog.id).label("record_id"),
        func.count(col(LLMAuditLog.id)).over().label("total_count"),
        func.row_number()
        .over(order_by=(order_expression, col(LLMAuditLog.id).desc()))
        .label("page_order"),
    )
    page_query = (
        _apply_filters(page_query, filters)
        .order_by(order_expression, col(LLMAuditLog.id).desc())
        .limit(limit)
        .offset(offset)
        .subquery("dashboard_record_page")
    )
    query = (
        select(
            col(LLMAuditLog.id),
            col(LLMAuditLog.created_at),
            col(LLMAuditLog.task_id),
            col(LLMAuditLog.session_id),
            col(LLMAuditLog.project_id),
            col(Project.title).label("project_title"),
            col(LLMAuditLog.chapter_id),
            col(LLMAuditLog.revision_id),
            col(LLMAuditLog.category),
            col(LLMAuditLog.operation),
            col(LLMAuditLog.model_id),
            col(LLMAuditLog.model_provider),
            col(LLMAuditLog.model_name),
            col(LLMAuditLog.tokens_input),
            col(LLMAuditLog.tokens_output),
            col(LLMAuditLog.tokens_total),
            col(LLMAuditLog.token_cache),
            col(LLMAuditLog.latency_ms),
            col(LLMAuditLog.first_token_ms),
            col(LLMAuditLog.status),
            col(LLMAuditLog.error_type),
            col(LLMAuditLog.error_message),
            col(LLMAuditLog.error_status_code),
            col(LLMAuditLog.tool_calls_count),
            (
                func.coalesce(func.length(func.trim(col(LLMAuditLog.request_messages))), 0) > 0
            ).label("has_request_messages"),
            col(LLMAuditLog.tool_references),
            col(LLMAuditLog.response_content),
            col(LLMAuditLog.response_tool_calls),
            page_query.c.total_count,
        )
        .join(page_query, col(LLMAuditLog.id) == page_query.c.record_id)
        .outerjoin(Project, col(Project.id) == col(LLMAuditLog.project_id))
        .order_by(page_query.c.page_order)
    )
    result = await session.execute(_apply_filters(query, filters))
    rows = result.all()
    records = [
        DashboardRecordRow(
            id=row.id,
            created_at=row.created_at,
            task_id=row.task_id,
            session_id=row.session_id,
            project_id=row.project_id,
            project_title=row.project_title,
            chapter_id=row.chapter_id,
            revision_id=row.revision_id,
            category=row.category,
            operation=row.operation,
            model_id=row.model_id,
            model_provider=row.model_provider,
            model_name=row.model_name,
            tokens_input=row.tokens_input or 0,
            tokens_output=row.tokens_output or 0,
            tokens_total=row.tokens_total or 0,
            token_cache=row.token_cache or 0,
            latency_ms=row.latency_ms,
            first_token_ms=row.first_token_ms,
            status=row.status,
            error_type=row.error_type,
            error_message=row.error_message,
            error_status_code=row.error_status_code,
            tool_calls_count=row.tool_calls_count or 0,
            has_request_messages=bool(row.has_request_messages),
            tool_references=row.tool_references,
            response_content=row.response_content,
            response_tool_calls=row.response_tool_calls,
        )
        for row in rows
    ]
    total = int(rows[0].total_count) if rows else None
    return records, total


async def get_record_prompt(
    session: AsyncSession,
    record_id: str,
) -> DashboardRecordPromptRow | None:
    """获取单条审计记录的输入提示词。"""
    query = select(
        col(LLMAuditLog.id),
        col(LLMAuditLog.request_messages),
    ).where(col(LLMAuditLog.id) == record_id)
    row = (await session.execute(query)).first()
    if row is None:
        return None
    return DashboardRecordPromptRow(
        id=row.id,
        request_messages=row.request_messages,
    )


async def get_filter_options(session: AsyncSession) -> DashboardFilterOptionsRow:
    """通过一次查询获取全部全局筛选选项。"""
    option_queries = [
        _distinct_option_query("project_ids", col(LLMAuditLog.project_id)),
        _distinct_option_query("model_providers", col(LLMAuditLog.model_provider)),
        _distinct_option_query("model_ids", col(LLMAuditLog.model_id)),
        _distinct_option_query("categories", col(LLMAuditLog.category)),
        _distinct_option_query("operations", col(LLMAuditLog.operation)),
        _distinct_option_query("statuses", col(LLMAuditLog.status)),
        select(
            literal("project_options").label("kind"),
            col(LLMAuditLog.project_id).label("value"),
            func.coalesce(col(Project.title), col(LLMAuditLog.project_id)).label("label"),
        )
        .outerjoin(Project, col(Project.id) == col(LLMAuditLog.project_id))
        .where(col(LLMAuditLog.project_id).is_not(None))
        .distinct(),
        select(
            literal("model_options").label("kind"),
            col(LLMAuditLog.model_id).label("value"),
            func.coalesce(col(LLMAuditLog.model_name), col(LLMAuditLog.model_id)).label("label"),
        )
        .where(col(LLMAuditLog.model_id).is_not(None))
        .distinct(),
    ]
    result = await session.execute(union_all(*option_queries))
    simple_values: dict[str, list[str]] = {
        "project_ids": [],
        "model_providers": [],
        "model_ids": [],
        "categories": [],
        "operations": [],
        "statuses": [],
    }
    project_options: list[FilterOptionRow] = []
    model_options: list[FilterOptionRow] = []
    for row in result.all():
        if row.kind in simple_values:
            if row.value:
                simple_values[row.kind].append(row.value)
        elif row.kind == "project_options" and row.value:
            project_options.append(FilterOptionRow(value=row.value, label=row.label))
        elif row.kind == "model_options" and row.value:
            model_options.append(FilterOptionRow(value=row.value, label=row.label))

    for values in simple_values.values():
        values.sort()
    project_options.sort(key=lambda item: item.label)
    model_options.sort(key=lambda item: item.label)
    return DashboardFilterOptionsRow(
        **simple_values,
        project_options=project_options,
        model_options=model_options,
    )


def _distinct_option_query(kind: str, column: Any):
    """构建一个带类型标识的去重筛选项查询。"""
    return select(
        literal(kind).label("kind"),
        cast(column, String).label("value"),
        literal(None, type_=String()).label("label"),
    ).where(column.is_not(None)).distinct()
