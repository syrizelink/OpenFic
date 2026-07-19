# -*- coding: utf-8 -*-
"""
Agent API Schemas。
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.agent_runtime.types import DEFAULT_AGENT_MAX_ITERATIONS
from app.api.schemas.task import TaskMessage
from app.models.clients.model_params import ReasoningEffort

class AgentSessionCreateRequest(BaseModel):
    """创建 Agent 会话请求。"""

    project_id: str = Field(..., description="项目ID")
    model_id: str = Field(..., description="模型ID")
    max_iterations: int = Field(
        default=DEFAULT_AGENT_MAX_ITERATIONS,
        ge=1,
        le=DEFAULT_AGENT_MAX_ITERATIONS,
        description="最大迭代次数",
    )
    agent_key: str = Field(
        default="primary",
        description="主智能体标识，用于选择启用的 primary agent",
    )
    reasoning_effort: ReasoningEffort | None = Field(
        default=None,
        description="当前会话推理强度，仅 reasoning 模型可用",
    )

    model_config = {"extra": "forbid"}


class AgentSessionCreateResponse(BaseModel):
    """创建 Agent 会话响应。"""

    session_id: str = Field(..., description="会话ID")
    project_id: str = Field(..., description="项目ID")
    status: str = Field(..., description="状态")
    task_id: str = Field(..., description="创建的任务ID")
    task_title: str = Field(..., description="创建的任务标题")
    task_created_at: str = Field(..., description="任务创建时间")
    task_updated_at: str = Field(..., description="任务更新时间")
    agent_key: str = Field(..., description="当前会话使用的主智能体标识")


class AgentSendMessageRequest(BaseModel):
    """发送用户消息请求。"""

    message: str = Field(..., description="用户消息内容")
    model_id: str | None = Field(default=None, description="下一轮执行使用的模型ID")
    reasoning_effort: ReasoningEffort | None = Field(
        default=None,
        description="当前轮推理强度，仅 reasoning 模型可用",
    )


class AgentPendingMessageResponse(BaseModel):
    """运行中排队的用户消息。"""

    message_id: str = Field(..., description="待消费消息ID")
    content: str = Field(..., description="待消费消息内容")
    created_at: str = Field(..., description="进入 pending 的时间")


class AgentSendMessageResponse(BaseModel):
    """发送用户消息响应。"""

    success: bool = Field(..., description="是否成功")
    session_id: str = Field(..., description="会话ID")
    message: str = Field(..., description="结果消息")
    queued: bool = Field(default=False, description="是否进入 pending 队列")
    model_updated: bool = Field(default=False, description="是否已更新下一轮执行模型")
    pending_message: AgentPendingMessageResponse | None = Field(
        default=None,
        description="进入 pending 的消息负载",
    )


class AgentCancelPendingMessageRequest(BaseModel):
    """取消待消费用户消息请求。"""

    message_id: str = Field(..., description="待取消的 pending message ID")


class AgentCancelPendingMessageResponse(BaseModel):
    """取消待消费用户消息响应。"""

    success: bool = Field(..., description="是否成功")
    session_id: str = Field(..., description="会话ID")
    message_id: str = Field(..., description="被取消的 pending message ID")
    restored_message_content: str = Field(..., description="恢复到输入框的消息内容")


class AgentCompactionResponse(BaseModel):
    """手动压缩响应。"""

    success: bool = Field(..., description="是否成功")
    session_id: str = Field(..., description="会话ID")
    compaction_id: str = Field(..., description="压缩记录ID")
    start_seq: int = Field(..., description="压缩窗口起始消息序号")
    end_seq: int = Field(..., description="压缩窗口结束消息序号")
    source_input_tokens: int = Field(default=0, description="源窗口输入 token 数")
    summary_tokens: int = Field(default=0, description="摘要 token 数")


class AgentQuestionAnswerRequest(BaseModel):
    """提交 Agent 澄清问题回答请求。"""

    action_id: str = Field(..., description="澄清请求ID")
    answer: list["AgentQuestionAnswerItem"] = Field(
        ..., min_length=1, description="澄清问题回答"
    )


class AgentQuestionAnswerItem(BaseModel):
    """单个澄清问题回答。"""

    question: str = Field(..., min_length=1, description="问题标题")
    answer: str = Field(..., min_length=1, description="选项标签或用户输入")


class AgentToolApprovalRequest(BaseModel):
    """Agent工具审批请求。"""

    approval_id: str = Field(..., description="审批ID")
    approved: bool = Field(..., description="是否批准")


class AgentToolMetadataResponse(BaseModel):
    """Agent 工具权限元数据。"""

    key: str = Field(..., description="权限配置键")
    is_readonly: bool = Field(..., description="是否只读")


class AgentSessionStateResponse(BaseModel):
    """会话状态响应。"""

    session_id: str = Field(..., description="会话ID")
    state: dict = Field(..., description="状态信息")
    is_running: bool = Field(default=False, description="会话是否仍有后台运行任务")


class ActiveSubagentStateResponse(BaseModel):
    """父会话下活跃子代理的只读状态行。"""

    child_run_id: str = Field(..., description="子运行ID")
    child_thread_id: str = Field(..., description="子线程ID")
    agent_key: str = Field(..., description="子代理标识")
    agent_number: str | None = Field(default=None, description="子代理编号")
    status: str = Field(..., description="子运行状态")
    queued_messages: int = Field(..., description="待处理请求数")
    is_active: bool = Field(..., description="子运行是否仍活跃")
    pending_approval: dict | None = Field(
        default=None,
        description="当前待处理的工具审批负载",
    )


class SubagentSessionResponse(BaseModel):
    """子代理会话详情。"""

    child_run_id: str = Field(..., description="子运行ID")
    parent_session_id: str = Field(..., description="父会话ID")
    parent_task_id: str = Field(..., description="父任务ID")
    parent_thread_id: str = Field(..., description="父线程ID")
    child_thread_id: str = Field(..., description="子线程ID")
    agent_key: str = Field(..., description="子代理标识")
    agent_number: str | None = Field(default=None, description="子代理编号")
    dispatch_id: str = Field(..., description="调度ID")
    tool_call_id: str = Field(..., description="工具调用ID")
    status: str = Field(..., description="子运行状态")
    queued_messages: int = Field(..., description="待处理请求数")
    is_active: bool = Field(..., description="子运行是否活跃")
    is_running: bool = Field(..., description="子运行是否仍在后台执行")
    request: dict = Field(default_factory=dict, description="子运行请求负载")
    result: dict | None = Field(default=None, description="子运行结果负载")
    pending_approval: dict | None = Field(default=None, description="待用户处理的审批负载")
    error: str | None = Field(default=None, description="错误信息")
    metadata: dict = Field(default_factory=dict, description="子运行元数据")
    token_input: int = Field(default=0, description="当前子会话最近一次输入 token")
    token_output: int = Field(default=0, description="当前子会话最近一次输出 token")
    token_cache: int = Field(default=0, description="当前子会话最近一次缓存 token")
    context_input_tokens: int = Field(
        default=0,
        description="当前子会话最近一次上下文输入 token",
    )
    context_length: int = Field(default=0, description="当前子会话上下文窗口大小")
    started_at: datetime | None = Field(default=None, description="开始时间")
    completed_at: datetime | None = Field(default=None, description="完成时间")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    messages: list[TaskMessage] = Field(
        default_factory=list,
        description="子线程 transcript 消息",
    )


class AgentRollbackRequest(BaseModel):
    """Agent回滚请求。"""

    revision_id: str = Field(..., description="目标revision ID")

    model_config = {"extra": "forbid"}


class AgentRollbackResponse(BaseModel):
    """Agent回滚响应。"""

    success: bool = Field(..., description="是否成功")
    session_id: str = Field(..., description="会话ID")
    revision_id: str | None = Field(None, description="rollback revision ID")
    affected_chapters: list[str] = Field(
        default_factory=list, description="受影响的章节ID列表"
    )
    affected_notes: list[str] = Field(
        default_factory=list, description="受影响的笔记ID列表"
    )
    affected_note_categories: list[str] = Field(
        default_factory=list, description="受影响的笔记分类ID列表"
    )
    affected_world_entries: list[str] = Field(
        default_factory=list, description="受影响的世界书条目ID列表"
    )
    restored_message_content: str = Field(..., description="恢复的消息内容")


class AgentForkRequest(BaseModel):
    """Agent会话分叉请求。"""

    source_revision_id: str = Field(..., description="分叉来源用户消息 revision ID")
    model_id: str = Field(..., description="Fork 会话后续使用的模型 ID")

    model_config = {"extra": "forbid"}


class AgentForkResponse(BaseModel):
    """Agent会话分叉响应。"""

    session_id: str = Field(..., description="新 Agent 会话 ID")
    task_id: str = Field(..., description="新 Task ID")
    task_title: str = Field(..., description="新 Task 标题")
    task_created_at: str = Field(..., description="新 Task 创建时间")
    task_updated_at: str = Field(..., description="新 Task 更新时间")


class AgentCancelResponse(BaseModel):
    """Agent取消响应。"""

    success: bool = Field(..., description="是否成功")
    session_id: str = Field(..., description="会话ID")
    message: str = Field(..., description="取消消息")
