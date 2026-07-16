# -*- coding: utf-8 -*-
"""
Dashboard Repository - LLM API 仪表盘只读查询。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
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
class DashboardMetricRow:
    """用于仪表盘聚合的轻量审计行。"""

    id: str
    created_at: datetime
    project_id: str
    project_title: str | None
    model_id: str
    model_name: str | None
    tokens_input: int
    tokens_output: int
    tokens_total: int
    latency_ms: int | None
    first_token_ms: int | None
    status: str


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


async def list_metric_rows(
    session: AsyncSession,
    filters: DashboardFilters,
) -> list[DashboardMetricRow]:
    """获取聚合所需的轻量字段，避免反复扫描和加载大文本列。"""
    query = select(
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
    )
    query = query.outerjoin(Project, col(Project.id) == col(LLMAuditLog.project_id))
    result = await session.execute(_apply_filters(query, filters))
    return [
        DashboardMetricRow(
            id=row.id,
            created_at=row.created_at,
            project_id=row.project_id,
            project_title=row.project_title,
            model_id=row.model_id,
            model_name=row.model_name,
            tokens_input=row.tokens_input or 0,
            tokens_output=row.tokens_output or 0,
            tokens_total=row.tokens_total or 0,
            latency_ms=row.latency_ms,
            first_token_ms=row.first_token_ms,
            status=row.status,
        )
        for row in result.all()
    ]


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
) -> list[DashboardRecordRow]:
    """获取筛选后的审计记录。"""
    sort_column = SORT_COLUMNS.get(sort_by, LLMAuditLog.created_at)
    order_expression = (
        col(sort_column).asc() if sort_order == "asc" else col(sort_column).desc()
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
            col(LLMAuditLog.response_content),
            col(LLMAuditLog.response_tool_calls),
        )
        .outerjoin(Project, col(Project.id) == col(LLMAuditLog.project_id))
        .order_by(order_expression, col(LLMAuditLog.id).desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(_apply_filters(query, filters))
    return [
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
            response_content=row.response_content,
            response_tool_calls=row.response_tool_calls,
        )
        for row in result.all()
    ]


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


async def list_distinct_values(
    session: AsyncSession,
    column_name: str,
) -> list[str]:
    """获取字段去重值。"""
    column = getattr(LLMAuditLog, column_name)
    query = select(column).where(column.is_not(None)).distinct().order_by(column)
    result = await session.execute(query)
    return [value for value in result.scalars().all() if value]


async def list_project_filter_options(session: AsyncSession) -> list[FilterOptionRow]:
    """获取项目筛选显示项。"""
    query: Any = (
        select(
            col(LLMAuditLog.project_id).label("value"),
            func.coalesce(col(Project.title), col(LLMAuditLog.project_id)).label("label"),
        )
        .outerjoin(Project, col(Project.id) == col(LLMAuditLog.project_id))
        .where(col(LLMAuditLog.project_id).is_not(None))
        .distinct()
        .order_by("label")
    )
    result = await session.execute(query)
    return [FilterOptionRow(value=row.value, label=row.label) for row in result.all() if row.value]


async def list_model_filter_options(session: AsyncSession) -> list[FilterOptionRow]:
    """获取模型筛选显示项。"""
    query: Any = (
        select(
            col(LLMAuditLog.model_id).label("value"),
            func.coalesce(col(LLMAuditLog.model_name), col(LLMAuditLog.model_id)).label("label"),
        )
        .where(col(LLMAuditLog.model_id).is_not(None))
        .distinct()
        .order_by("label")
    )
    result = await session.execute(query)
    return [FilterOptionRow(value=row.value, label=row.label) for row in result.all() if row.value]
