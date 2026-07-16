# -*- coding: utf-8 -*-
"""
Audit Router - 审计日志API路由。
"""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.audit import (
    LLMAuditLogListResponse,
    LLMAuditLogResponse,
    TaskAuditAggregation,
    ToolCallResult,
)
from app.audit.repo import LLMAuditLogRepo
from app.storage.database import get_session

router = APIRouter(tags=["Audit"])


def serialize_audit_log(log) -> LLMAuditLogResponse:
    """序列化审计日志。"""
    request_messages = None
    if log.request_messages:
        try:
            request_messages = json.loads(log.request_messages)
        except json.JSONDecodeError:
            request_messages = None

    tool_references = None
    if log.tool_references:
        try:
            tool_references = json.loads(log.tool_references)
        except json.JSONDecodeError:
            tool_references = None

    response_tool_calls = None
    if log.response_tool_calls:
        try:
            response_tool_calls = json.loads(log.response_tool_calls)
        except json.JSONDecodeError:
            response_tool_calls = None

    tool_call_results = None
    if log.tool_call_results:
        try:
            tool_call_results = [
                ToolCallResult(**tc) for tc in json.loads(log.tool_call_results)
            ]
        except (json.JSONDecodeError, TypeError):
            tool_call_results = None

    return LLMAuditLogResponse(
        id=log.id,
        created_at=log.created_at,
        task_id=log.task_id,
        session_id=log.session_id,
        parent_session_id=log.parent_session_id,
        child_run_id=log.child_run_id,
        project_id=log.project_id,
        chapter_id=log.chapter_id,
        revision_id=log.revision_id,
        category=log.category,
        operation=log.operation,
        call_sequence=log.call_sequence,
        model_id=log.model_id,
        model_provider=log.model_provider,
        model_name=log.model_name,
        request_messages=request_messages,
        tool_references=tool_references,
        response_content=log.response_content,
        response_tool_calls=response_tool_calls,
        tool_call_results=tool_call_results,
        tokens_input=log.tokens_input,
        tokens_output=log.tokens_output,
        tokens_total=log.tokens_total,
        token_cache=log.token_cache,
        latency_ms=log.latency_ms,
        first_token_ms=log.first_token_ms,
        status=log.status,
        error_type=log.error_type,
        error_message=log.error_message,
        error_status_code=log.error_status_code,
        tool_calls_count=log.tool_calls_count,
        tool_calls_success_count=log.tool_calls_success_count,
        tool_calls_failed_count=log.tool_calls_failed_count,
    )


@router.get("/tasks/{task_id}/audit-logs", response_model=LLMAuditLogListResponse)
async def list_task_audit_logs(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> LLMAuditLogListResponse:
    """获取Task的所有审计日志。"""
    repo = LLMAuditLogRepo(session)
    logs = await repo.list_by_task(task_id)
    items = [serialize_audit_log(log) for log in logs]
    return LLMAuditLogListResponse(items=items, total=len(items))


@router.get("/tasks/{task_id}/audit-aggregation", response_model=TaskAuditAggregation)
async def get_task_audit_aggregation(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> TaskAuditAggregation:
    """获取Task级别的审计聚合数据。"""
    repo = LLMAuditLogRepo(session)
    aggregation = await repo.aggregate_by_task(task_id)
    if not aggregation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} 的审计数据不存在",
        )
    return TaskAuditAggregation(
        task_id=aggregation.task_id,
        llm_calls_total=aggregation.llm_calls_total,
        revisions_count=aggregation.revisions_count,
        tokens_input_total=aggregation.tokens_input_total,
        tokens_output_total=aggregation.tokens_output_total,
        tokens_grand_total=aggregation.tokens_grand_total,
        duration_ms=aggregation.duration_ms,
        tool_calls_grand_total=aggregation.tool_calls_grand_total,
        has_error=aggregation.has_error,
    )


@router.get(
    "/audit-logs/session/{session_id}", response_model=LLMAuditLogListResponse
)
async def list_session_audit_logs(
    session_id: str,
    db_session: AsyncSession = Depends(get_session),
) -> LLMAuditLogListResponse:
    """获取Agent会话的所有审计日志。"""
    repo = LLMAuditLogRepo(db_session)
    logs = await repo.list_by_session(session_id)
    items = [serialize_audit_log(log) for log in logs]
    return LLMAuditLogListResponse(items=items, total=len(items))


@router.get("/audit-logs/{audit_id}", response_model=LLMAuditLogResponse)
async def get_audit_log(
    audit_id: str,
    session: AsyncSession = Depends(get_session),
) -> LLMAuditLogResponse:
    """获取单条审计日志详情。"""
    repo = LLMAuditLogRepo(session)
    log = await repo.get_by_id(audit_id)
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"审计日志 {audit_id} 不存在",
        )
    return serialize_audit_log(log)
