# -*- coding: utf-8 -*-
"""
Dashboard Router - LLM API 统计仪表盘 API。
"""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.dashboard import (
    DashboardAuditRecord,
    DashboardBreakdownItem,
    DashboardFilterOptions,
    DashboardFilterOptionItem,
    DashboardModelTimeSeriesPoint,
    DashboardRecordList,
    DashboardRecordPrompt,
    DashboardRecordsResponse,
    DashboardSummary,
    DashboardStatsResponse,
    WritingActivitySummary,
    WritingActivityTimeSeriesPoint,
    WritingDashboardResponse,
)
from app.storage.database import get_session
from app.storage.repos.dashboard_repo import (
    BreakdownRow,
    FilterOptionRow,
    DashboardRecordRow,
    ModelTimeSeriesRow,
)
from app.storage.repos.writing_activity_repo import WritingActivityTimeSeriesRow
from app.storage.services import dashboard_service
from app.storage.services import writing_activity_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _serialize_record(record: DashboardRecordRow) -> DashboardAuditRecord:
    return DashboardAuditRecord(
        id=record.id,
        created_at=record.created_at,
        task_id=record.task_id,
        session_id=record.session_id,
        project_id=record.project_id,
        project_title=record.project_title,
        chapter_id=record.chapter_id,
        revision_id=record.revision_id,
        category=record.category,
        operation=record.operation,
        model_id=record.model_id,
        model_provider=record.model_provider,
        model_name=record.model_name,
        tokens_input=record.tokens_input,
        tokens_output=record.tokens_output,
        tokens_total=record.tokens_total,
        token_cache=record.token_cache,
        latency_ms=record.latency_ms,
        first_token_ms=record.first_token_ms,
        status=record.status,
        error_type=record.error_type,
        error_message=record.error_message,
        error_status_code=record.error_status_code,
        tool_calls_count=record.tool_calls_count,
        has_request_messages=record.has_request_messages,
        tool_references=record.tool_references,
        response_content=record.response_content,
        response_tool_calls=record.response_tool_calls,
    )


def _serialize_breakdowns(items: list[BreakdownRow]) -> list[DashboardBreakdownItem]:
    return [
        DashboardBreakdownItem(
            key=item.key,
            label=item.label,
            calls=item.calls,
            tokens_total=item.tokens_total,
        )
        for item in items
    ]


def _serialize_filter_options(items: list[FilterOptionRow]) -> list[DashboardFilterOptionItem]:
    return [DashboardFilterOptionItem(value=item.value, label=item.label) for item in items]


def _serialize_options(options: dashboard_service.DashboardFilterOptionsResult) -> DashboardFilterOptions:
    return DashboardFilterOptions(
        project_ids=options.project_ids,
        model_providers=options.model_providers,
        model_ids=options.model_ids,
        categories=options.categories,
        operations=options.operations,
        statuses=options.statuses,
        project_options=_serialize_filter_options(options.project_options),
        model_options=_serialize_filter_options(options.model_options),
    )


def _serialize_model_time_series(
    items: list[ModelTimeSeriesRow],
) -> list[DashboardModelTimeSeriesPoint]:
    return [DashboardModelTimeSeriesPoint(**item.__dict__) for item in items]


def _serialize_writing_time_series(
    items: list[WritingActivityTimeSeriesRow],
) -> list[WritingActivityTimeSeriesPoint]:
    return [WritingActivityTimeSeriesPoint(**item.__dict__) for item in items]


@router.get("/llm-api/stats", response_model=DashboardStatsResponse)
async def get_llm_api_stats_dashboard(
    project_id: str | None = Query(default=None),
    model_provider: str | None = Query(default=None),
    model_id: str | None = Query(default=None),
    category: str | None = Query(default=None),
    operation: str | None = Query(default=None),
    status: str | None = Query(default=None),
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> DashboardStatsResponse:
    """获取 LLM API 仪表盘统计。"""
    filters = dashboard_service.build_filters(
        project_id=project_id,
        model_provider=model_provider,
        model_id=model_id,
        category=category,
        operation=operation,
        status=status,
        start_at=start_at,
        end_at=end_at,
    )
    result = await dashboard_service.get_stats_dashboard(session, filters)
    return DashboardStatsResponse(
        summary=DashboardSummary(**result.summary.__dict__),
        model_time_series=_serialize_model_time_series(result.model_time_series),
        by_model=_serialize_breakdowns(result.by_model),
        by_project=_serialize_breakdowns(result.by_project),
        options=_serialize_options(result.options),
    )


@router.get("/llm-api/records", response_model=DashboardRecordsResponse)
async def get_llm_api_records_dashboard(
    project_id: str | None = Query(default=None),
    model_provider: str | None = Query(default=None),
    model_id: str | None = Query(default=None),
    category: str | None = Query(default=None),
    operation: str | None = Query(default=None),
    status: str | None = Query(default=None),
    task_id: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=5, le=100),
    sort_by: Literal[
        "created_at",
        "tokens_input",
        "tokens_output",
        "tokens_total",
        "latency_ms",
        "first_token_ms",
        "tool_calls_count",
    ] = Query(default="created_at"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    session: AsyncSession = Depends(get_session),
) -> DashboardRecordsResponse:
    """获取 LLM API 调用记录列表。"""
    filters = dashboard_service.build_filters(
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
        search=search,
    )
    result = await dashboard_service.get_records_dashboard(
        session,
        filters,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return DashboardRecordsResponse(
        options=_serialize_options(result.options),
        records=DashboardRecordList(
            items=[_serialize_record(record) for record in result.records.items],
            total=result.records.total,
            page=result.records.page,
            page_size=result.records.page_size,
        ),
    )


@router.get("/llm-api/records/{record_id}/prompt", response_model=DashboardRecordPrompt)
async def get_llm_api_record_prompt(
    record_id: str,
    session: AsyncSession = Depends(get_session),
) -> DashboardRecordPrompt:
    """获取单条 LLM API 调用记录的输入提示词。"""
    record = await dashboard_service.get_record_prompt(session, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="调用记录不存在")
    return DashboardRecordPrompt(
        id=record.id,
        request_messages=record.request_messages,
    )


@router.get("/writing", response_model=WritingDashboardResponse)
async def get_writing_dashboard(
    project_id: str | None = Query(default=None),
    source: Literal["user", "agent", "import"] | None = Query(default=None),
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    timezone: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> WritingDashboardResponse:
    """获取写作活动统计。"""
    filters = writing_activity_service.build_filters(
        project_id=project_id,
        source=source,
        start_at=start_at,
        end_at=end_at,
        timezone=timezone,
    )
    result = await writing_activity_service.get_dashboard(session, filters)
    return WritingDashboardResponse(
        summary=WritingActivitySummary(**result.summary.__dict__),
        time_series=_serialize_writing_time_series(result.time_series),
    )
