# -*- coding: utf-8 -*-
"""
Agent Audit Log 数据模型 - Agent审计日志。
"""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.core.ids import generate_id


class AgentAuditLog(SQLModel, table=True):
    """
    Agent审计日志模型。

    记录每次LLM API调用的详细信息，用于审计和统计分析。

    Attributes:
        id: 审计记录唯一标识符（nanoid）。
        created_at: 记录创建时间。
        task_id: 关联的Task ID，用于三级聚合查询。
        session_id: Agent会话ID。
        parent_session_id: 子代理所属父会话ID；主会话调用为空。
        child_run_id: 子代理运行ID；主会话调用为空。
        project_id: 项目ID。
        chapter_id: 章节ID（可能为空）。
        revision_id: 本次调用产生的Revision ID，用于二级聚合查询。
        agent_node: Agent节点名称（clarifier/designer/writer/reviewer）。
        call_sequence: 同一session内的调用顺序号。
        model_id: 使用的模型ID。
        model_provider: 模型提供商类型。
        model_name: 模型名称。
        request_messages: 发送给LLM的完整消息列表（JSON格式）。
        response_content: LLM返回的文本内容。
        response_tool_calls: LLM请求调用的工具列表（JSON格式）。
        tool_call_results: 工具执行后的返回结果（JSON格式）。
        tokens_input: 输入token消耗量。
        tokens_output: 输出token消耗量。
        tokens_total: 总token消耗量。
        token_cache: API 返回的缓存命中 token 数。
        latency_ms: API调用耗时（毫秒）。
        first_token_ms: 首Token延迟TTFT（毫秒）。
        status: 调用结果状态。
        error_type: 错误分类。
        error_message: 错误消息详情。
        error_status_code: HTTP错误状态码。
        tool_calls_count: LLM请求的工具调用总数。
        tool_calls_success_count: 成功执行的工具数。
        tool_calls_failed_count: 执行失败的工具数。
        metadata: 扩展元数据（JSON格式）。
    """

    __tablename__ = "agent_audit_logs"

    id: str = Field(default_factory=generate_id, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)

    task_id: str | None = Field(default=None, index=True, foreign_key="tasks.id")
    session_id: str | None = Field(default=None, index=True)
    parent_session_id: str | None = Field(default=None, index=True)
    child_run_id: str | None = Field(default=None, index=True)
    project_id: str = Field(index=True, foreign_key="projects.id")
    chapter_id: str | None = Field(default=None, index=True, foreign_key="chapters.id")
    revision_id: str | None = Field(
        default=None, index=True, foreign_key="revisions.id"
    )

    agent_node: str = Field(max_length=50, index=True)
    call_sequence: int | None = Field(default=None)

    model_id: str = Field(index=True)
    model_provider: str | None = Field(default=None, max_length=50, index=True)
    model_name: str | None = Field(default=None, max_length=100)

    request_messages: str | None = Field(default=None)
    response_content: str | None = Field(default=None)
    response_tool_calls: str | None = Field(default=None)
    tool_call_results: str | None = Field(default=None)

    tokens_input: int = Field(default=0)
    tokens_output: int = Field(default=0)
    tokens_total: int = Field(default=0)
    token_cache: int = Field(default=0)

    latency_ms: int | None = Field(default=None)
    first_token_ms: int | None = Field(default=None)

    status: str = Field(max_length=20, index=True)
    error_type: str | None = Field(default=None, max_length=50)
    error_message: str | None = Field(default=None)
    error_status_code: int | None = Field(default=None)

    tool_calls_count: int = Field(default=0)
    tool_calls_success_count: int = Field(default=0)
    tool_calls_failed_count: int = Field(default=0)

    extra_data: str | None = Field(default=None)
