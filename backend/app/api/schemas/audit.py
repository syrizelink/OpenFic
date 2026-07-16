# -*- coding: utf-8 -*-
"""
Audit API Schemas - 审计日志请求/响应模型。
"""

from datetime import datetime

from pydantic import BaseModel, Field


class ToolCallResult(BaseModel):
    """工具调用结果。"""

    tool_name: str = Field(description="工具名称")
    tool_args: dict = Field(description="工具参数")
    result: dict | None = Field(default=None, description="执行结果")
    success: bool = Field(description="是否成功")
    latency_ms: int = Field(default=0, description="耗时（毫秒）")


class LLMAuditLogResponse(BaseModel):
    """LLM 审计日志响应。"""

    id: str = Field(description="审计记录ID")
    created_at: datetime = Field(description="创建时间")

    task_id: str | None = Field(default=None, description="Task ID")
    session_id: str | None = Field(default=None, description="Agent会话ID")
    parent_session_id: str | None = Field(
        default=None,
        description="父会话ID；主会话调用为空",
    )
    child_run_id: str | None = Field(
        default=None,
        description="子代理运行ID；主会话调用为空",
    )
    project_id: str = Field(description="项目ID")
    chapter_id: str | None = Field(default=None, description="章节ID")
    revision_id: str | None = Field(default=None, description="Revision ID")

    category: str = Field(description="调用分类")
    operation: str = Field(description="调用操作")
    call_sequence: int | None = Field(default=None, description="调用顺序号")

    model_id: str = Field(description="模型ID")
    model_provider: str | None = Field(default=None, description="模型提供商")
    model_name: str | None = Field(default=None, description="模型名称")

    request_messages: list[dict] | None = Field(
        default=None, description="请求消息列表"
    )
    response_content: str | None = Field(default=None, description="响应内容")
    response_tool_calls: list[dict] | None = Field(
        default=None, description="响应工具调用列表"
    )
    tool_call_results: list[ToolCallResult] | None = Field(
        default=None, description="工具调用结果列表"
    )

    tokens_input: int = Field(default=0, description="输入token数")
    tokens_output: int = Field(default=0, description="输出token数")
    tokens_total: int = Field(default=0, description="总token数")
    token_cache: int = Field(default=0, description="缓存命中token数")

    latency_ms: int | None = Field(default=None, description="API调用耗时（毫秒）")
    first_token_ms: int | None = Field(default=None, description="首Token延迟（毫秒）")

    status: str = Field(description="调用状态")
    error_type: str | None = Field(default=None, description="错误类型")
    error_message: str | None = Field(default=None, description="错误消息")
    error_status_code: int | None = Field(default=None, description="HTTP错误码")

    tool_calls_count: int = Field(default=0, description="工具调用总数")
    tool_calls_success_count: int = Field(default=0, description="成功工具调用数")
    tool_calls_failed_count: int = Field(default=0, description="失败工具调用数")


class LLMAuditLogListResponse(BaseModel):
    """LLM 审计日志列表响应。"""

    items: list[LLMAuditLogResponse] = Field(description="审计日志列表")
    total: int = Field(description="总数")


class TaskAuditAggregation(BaseModel):
    """Task级别审计聚合结果。"""

    task_id: str = Field(description="Task ID")
    llm_calls_total: int = Field(description="LLM调用总次数")
    revisions_count: int = Field(description="Revision数量")
    tokens_input_total: int = Field(description="输入token总数")
    tokens_output_total: int = Field(description="输出token总数")
    tokens_grand_total: int = Field(description="token总数")
    duration_ms: int = Field(description="总耗时（毫秒）")
    tool_calls_grand_total: int = Field(description="工具调用总数")
    has_error: bool = Field(description="是否有错误")
