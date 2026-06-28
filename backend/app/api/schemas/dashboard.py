# -*- coding: utf-8 -*-
"""
Dashboard API Schemas - LLM API 统计仪表盘响应模型。
"""

from datetime import datetime

from pydantic import BaseModel, Field


class DashboardSummary(BaseModel):
    """仪表盘总览指标。"""

    calls_total: int = Field(description="LLM API 调用总数")
    success_total: int = Field(description="成功调用数")
    tokens_total: int = Field(description="总 token 消耗")
    tokens_input_total: int = Field(description="输入 token 总数")
    tokens_output_total: int = Field(description="输出 token 总数")
    avg_latency_ms: float = Field(description="平均延迟（毫秒）")
    avg_first_token_ms: float = Field(description="平均首 token 延迟（毫秒）")


class DashboardModelTimeSeriesPoint(BaseModel):
    """按日期和模型聚合的趋势数据点。"""

    date: str = Field(description="日期，格式 YYYY-MM-DD")
    key: str = Field(description="模型键")
    label: str = Field(description="模型显示名称")
    calls: int = Field(description="调用次数")
    tokens_total: int = Field(description="总 token 消耗")
    avg_latency_ms: float = Field(description="平均延迟（毫秒）")


class DashboardBreakdownItem(BaseModel):
    """分组统计项。"""

    key: str = Field(description="分组键")
    label: str = Field(description="显示名称")
    calls: int = Field(description="调用次数")
    tokens_total: int = Field(description="总 token 消耗")


class DashboardFilterOptionItem(BaseModel):
    """筛选选项显示项。"""

    value: str = Field(description="筛选值")
    label: str = Field(description="显示名称")


class DashboardAuditRecord(BaseModel):
    """仪表盘审计记录列表项。"""

    id: str = Field(description="审计记录 ID")
    created_at: datetime = Field(description="创建时间")
    task_id: str | None = Field(default=None, description="Task ID")
    session_id: str | None = Field(default=None, description="会话 ID")
    project_id: str = Field(description="项目 ID")
    project_title: str | None = Field(default=None, description="项目标题")
    chapter_id: str | None = Field(default=None, description="章节 ID")
    revision_id: str | None = Field(default=None, description="Revision ID")
    agent_node: str = Field(description="Agent 节点")
    model_id: str = Field(description="模型 ID")
    model_provider: str | None = Field(default=None, description="模型提供商")
    model_name: str | None = Field(default=None, description="模型名称")
    tokens_input: int = Field(description="输入 token 数")
    tokens_output: int = Field(description="输出 token 数")
    tokens_total: int = Field(description="总 token 数")
    token_cache: int = Field(description="缓存命中 token 数")
    latency_ms: int | None = Field(default=None, description="API 调用延迟")
    first_token_ms: int | None = Field(default=None, description="首 token 延迟")
    status: str = Field(description="调用状态")
    error_type: str | None = Field(default=None, description="错误类型")
    error_message: str | None = Field(default=None, description="错误信息")
    error_status_code: int | None = Field(default=None, description="HTTP 错误码")
    tool_calls_count: int = Field(description="工具调用数")
    response_content: str | None = Field(default=None, description="模型输出文本")
    response_tool_calls: str | None = Field(default=None, description="模型工具调用 JSON")


class DashboardRecordPrompt(BaseModel):
    """调用记录输入提示词详情。"""

    id: str = Field(description="审计记录 ID")
    request_messages: str | None = Field(default=None, description="输入提示词消息 JSON")


class DashboardRecordList(BaseModel):
    """分页审计记录列表。"""

    items: list[DashboardAuditRecord] = Field(description="记录列表")
    total: int = Field(description="总记录数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页数量")


class WritingActivitySummary(BaseModel):
    """写作活动事件汇总。"""

    active_days: int = Field(description="有写作活动的天数")
    creative_chapters: int = Field(description="有创作活动的章节数")


class WritingActivityTimeSeriesPoint(BaseModel):
    """按日期聚合的写作活动数据点。"""

    date: str = Field(description="日期，格式 YYYY-MM-DD")
    user_word_delta: int = Field(description="用户编辑字数变化")
    agent_word_delta: int = Field(description="Agent 修改字数变化")
    import_word_delta: int = Field(description="导入初始化字数变化")


class WritingDashboardResponse(BaseModel):
    """写作统计仪表盘响应。"""

    summary: WritingActivitySummary = Field(description="写作活动汇总")
    time_series: list[WritingActivityTimeSeriesPoint] = Field(description="写作活动趋势")


class DashboardFilterOptions(BaseModel):
    """仪表盘筛选选项。"""

    project_ids: list[str] = Field(description="项目 ID 列表")
    model_providers: list[str] = Field(description="模型提供商列表")
    model_ids: list[str] = Field(description="模型 ID 列表")
    agent_nodes: list[str] = Field(description="Agent 节点列表")
    statuses: list[str] = Field(description="状态列表")
    project_options: list[DashboardFilterOptionItem] = Field(default_factory=list, description="项目筛选显示项")
    model_options: list[DashboardFilterOptionItem] = Field(default_factory=list, description="模型筛选显示项")


class DashboardStatsResponse(BaseModel):
    """LLM API 统计仪表盘响应。"""

    summary: DashboardSummary = Field(description="总览指标")
    model_time_series: list[DashboardModelTimeSeriesPoint] = Field(description="按模型聚合的时间趋势")
    by_model: list[DashboardBreakdownItem] = Field(description="按模型统计")
    by_project: list[DashboardBreakdownItem] = Field(description="按项目统计")
    options: DashboardFilterOptions = Field(description="筛选选项")


class DashboardRecordsResponse(BaseModel):
    """LLM API 调用记录响应。"""

    options: DashboardFilterOptions = Field(description="筛选选项")
    records: DashboardRecordList = Field(description="记录列表")
