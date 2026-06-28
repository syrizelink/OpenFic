# -*- coding: utf-8 -*-
"""
Task API Schemas - 任务请求/响应模型。
"""

from datetime import datetime
from pydantic import BaseModel, Field

from app.agent_runtime.modes import AgentMode


class TaskMessage(BaseModel):
    """任务消息。"""

    id: str = Field(description="消息ID")
    task_id: str | None = Field(default=None, description="任务ID")
    role: str = Field(description="消息角色：system、user、assistant 或 tool")
    agent_id: str | None = Field(default=None, description="消息来源的Agent ID")
    content: str = Field(description="消息内容")
    tool_calls: list[dict] = Field(default_factory=list, description="本条消息发起的工具调用列表")
    tool_call_id: str | None = Field(default=None, description="关联的工具调用ID")
    metadata: dict = Field(default_factory=dict, description="扩展元数据")
    message_type: str | None = Field(default=None, description="规范消息类型")
    message_status: str | None = Field(default=None, description="规范消息状态")
    display_channel: str | None = Field(default=None, description="规范显示通道")
    payload: dict = Field(default_factory=dict, description="规范消息负载")
    correlation_id: str | None = Field(default=None, description="关联消息/工具调用 ID")
    created_at: datetime = Field(description="消息创建时间")
    updated_at: datetime | None = Field(default=None, description="消息更新时间")


class TaskUpdateRequest(BaseModel):
    """更新任务请求。"""

    title: str | None = Field(default=None, description="任务标题")
    is_favorited: bool | None = Field(default=None, description="是否收藏")

    model_config = {"extra": "forbid"}


class TaskResponse(BaseModel):
    """任务响应。"""

    id: str = Field(description="任务 ID")
    project_id: str = Field(description="项目 ID")
    title: str = Field(description="任务标题")
    mode: AgentMode = Field(description="固定为单一 Agent runtime")
    messages: list[TaskMessage] = Field(description="对话消息列表")
    token_input: int = Field(default=0, description="输入 token 总数")
    token_output: int = Field(default=0, description="输出 token 总数")
    token_cache: int = Field(default=0, description="缓存命中 token 总数")
    context_input_tokens: int = Field(default=0, description="上一次 API 调用的输入 token 数")
    current_revision_id: str | None = Field(default=None, description="当前用户消息checkpoint对应的revision ID")
    current_message_id: str | None = Field(default=None, description="当前最新用户消息 ID")
    agent_session_id: str | None = Field(default=None, description="Agent会话ID")
    is_running: bool = Field(default=False, description="任务是否正在后台运行")
    is_favorited: bool = Field(description="是否收藏")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")


class TaskListItem(BaseModel):
    """任务列表项。"""

    id: str = Field(description="任务 ID")
    project_id: str = Field(description="项目 ID")
    title: str = Field(description="任务标题")
    mode: AgentMode = Field(description="固定为单一 Agent runtime")
    token_input: int = Field(default=0, description="输入 token 总数")
    token_output: int = Field(default=0, description="输出 token 总数")
    token_cache: int = Field(default=0, description="缓存命中 token 总数")
    context_input_tokens: int = Field(default=0, description="上一次 API 调用的输入 token 数")
    is_running: bool = Field(default=False, description="任务是否正在后台运行")
    is_favorited: bool = Field(description="是否收藏")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")


class TaskListResponse(BaseModel):
    """任务列表响应。"""

    items: list[TaskListItem] = Field(description="任务列表")
    total: int = Field(description="总数")
