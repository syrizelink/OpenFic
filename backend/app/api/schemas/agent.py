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
        default="build",
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


class AgentAttachmentResponse(BaseModel):
    """Agent 图片附件元数据。"""

    id: str = Field(..., description="附件 ID")
    session_id: str = Field(..., description="所属会话 ID")
    storage_name: str = Field(..., description="服务端存储相对路径")
    file_name: str = Field(..., description="原始文件名")
    mime_type: str = Field(..., description="图片 MIME 类型")
    size_bytes: int = Field(..., description="文件大小")
    width: int = Field(..., description="图片宽度")
    height: int = Field(..., description="图片高度")
    url: str = Field(..., description="图片展示地址")


class AgentSendMessageRequest(BaseModel):
    """发送用户消息请求。"""

    message: str = Field(default="", description="用户消息内容")
    attachments: list[str] = Field(default_factory=list, description="图片附件 ID 列表")
    model_id: str | None = Field(default=None, description="下一轮执行使用的模型ID")
    agent_key: str | None = Field(default=None, description="下一轮执行使用的主智能体标识")
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
    answer: list["AgentQuestionAnswerItem"] = Field(default_factory=list, description="澄清问题回答")
    skipped: bool = Field(default=False, description="是否忽略本次提问")


class AgentQuestionAnswerItem(BaseModel):
    """单个澄清问题回答。"""

    question: str = Field(..., min_length=1, description="问题标题")
    answer: str = Field(..., min_length=1, description="选项标签或用户输入")


class AgentToolApprovalRequest(BaseModel):
    """Agent工具审批请求。"""

    approval_id: str = Field(..., description="审批ID")
    approved: bool = Field(..., description="是否批准")


class AgentInterruptResponseItem(BaseModel):
    """单个并行中断响应。"""

    interrupt_id: str = Field(..., description="LangGraph 中断ID")
    action_type: str = Field(..., description="中断响应类型")
    approval_id: str | None = Field(default=None, description="工具审批ID")
    approved: bool | None = Field(default=None, description="是否批准工具")
    action_id: str | None = Field(default=None, description="澄清请求ID")
    answer: list[AgentQuestionAnswerItem] | None = Field(
        default=None,
        description="澄清问题回答",
    )
    skipped: bool | None = Field(default=None, description="是否忽略本次提问")


class AgentInterruptResumeRequest(BaseModel):
    """批量恢复同一轮并行中断。"""

    batch_id: str = Field(..., description="中断批次ID")
    responses: list[AgentInterruptResponseItem] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="本批全部中断响应",
    )


class AgentToolMetadataResponse(BaseModel):
    """Agent 工具权限元数据。"""

    key: str = Field(..., description="权限配置键")
    is_readonly: bool = Field(..., description="是否只读")


class AgentSessionStateResponse(BaseModel):
    """会话状态响应。"""

    session_id: str = Field(..., description="会话ID")
    state: dict = Field(..., description="状态信息")
    is_running: bool = Field(default=False, description="会话是否仍有后台运行任务")
    interrupts: list[dict] = Field(default_factory=list, description="待处理的可恢复中断")


class AgentChangeLineResponse(BaseModel):
    """单行 Agent 内容变更。"""

    type: str = Field(description="变更行类型：context、added 或 removed")
    before_line_number: int | None = Field(default=None, description="变更前行号")
    after_line_number: int | None = Field(default=None, description="变更后行号")
    text: str = Field(default="", description="变更行内容")


class AgentChangeSectionResponse(BaseModel):
    """Agent 内容变更。"""

    type: str = Field(description="变更类型：content")
    lines: list[AgentChangeLineResponse] = Field(default_factory=list, description="内容变更行")


class AgentChangeItemResponse(BaseModel):
    """单个 Agent 内容变更项。"""

    key: str = Field(description="变更实体键")
    kind: str = Field(description="实体类型")
    title: str = Field(description="实体标题")
    title_before: str | None = Field(default=None, description="标题变更前文本")
    title_after: str | None = Field(default=None, description="标题变更后文本")
    operation: str = Field(description="变更操作")
    path: list[str] = Field(default_factory=list, description="实体所属层级路径")
    sections: list[AgentChangeSectionResponse] = Field(default_factory=list, description="Diff 分段")
    added: int = Field(default=0, description="新增行数")
    removed: int = Field(default=0, description="删除行数")
    source_message_id: str = Field(description="来源工具消息 ID")
    source: str = Field(description="变更来源：primary、subagent 或 session")
    child_run_id: str | None = Field(default=None, description="来源子运行 ID")
    request_id: str | None = Field(default=None, description="来源子运行请求 ID")
    agent_key: str | None = Field(default=None, description="来源子代理标识")
    agent_number: str | None = Field(default=None, description="来源子代理编号")
    revision_id: str | None = Field(default=None, description="所属 revision ID")


class AgentChangeSummaryResponse(BaseModel):
    """Agent 内容变更汇总。"""

    item_count: int = Field(default=0, description="变更项数量")
    added: int = Field(default=0, description="新增行数")
    removed: int = Field(default=0, description="删除行数")
    items: list[AgentChangeItemResponse] = Field(default_factory=list, description="变更项")


class AgentSubagentRunChangesResponse(BaseModel):
    """单个 subagent 请求产生的变更。"""

    child_run_id: str = Field(description="子运行 ID")
    child_thread_id: str = Field(description="子线程 ID")
    request_id: str | None = Field(default=None, description="子运行请求 ID")
    child_user_message_id: str | None = Field(default=None, description="子运行用户消息 ID")
    agent_key: str = Field(description="子代理标识")
    agent_number: str | None = Field(default=None, description="子代理编号")
    changes: AgentChangeSummaryResponse = Field(description="该 subagent 请求的变更")


class AgentTurnChangesResponse(BaseModel):
    """主会话单个 turn 的变更。"""

    revision_id: str = Field(description="该 turn 的 revision ID")
    user_message_id: str | None = Field(default=None, description="触发 turn 的用户消息 ID")
    user_message_seq: int | None = Field(default=None, description="触发 turn 的用户消息序号")
    changes: AgentChangeSummaryResponse = Field(description="该 turn 的完整变更")
    subagent_runs: list[AgentSubagentRunChangesResponse] = Field(
        default_factory=list,
        description="该 turn 下的 subagent 变更",
    )


class AgentSessionChangesResponse(BaseModel):
    """主会话及其 subagent 的完整变更。"""

    session_id: str = Field(description="Agent 会话 ID")
    turns: list[AgentTurnChangesResponse] = Field(default_factory=list, description="按 turn 分组的变更")
    session_changes: AgentChangeSummaryResponse = Field(description="整个会话的变更")


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
    cost: float = Field(default=0.0, description="当前子会话最近一次费用（美元）")
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
    checkpoint_cleanup_failed: bool = Field(
        default=False,
        description=(
            "数据层回滚成功但 LangGraph checkpoint 清理失败；"
            "为 true 时会话状态层可能仍停留在回滚后的状态"
        ),
    )
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
    restored_attachments: list[AgentAttachmentResponse] = Field(
        default_factory=list,
        description="恢复到输入框的图片附件",
    )


class AgentForkRequest(BaseModel):
    """Agent会话分叉请求。"""

    source_revision_id: str = Field(..., description="分叉来源用户消息 revision ID")
    model_id: str = Field(..., description="Fork 会话后续使用的模型 ID")
    reasoning_effort: ReasoningEffort | None = Field(
        default=None,
        description="Fork 会话后续使用的推理强度",
    )

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
