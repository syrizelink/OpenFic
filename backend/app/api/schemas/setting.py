# -*- coding: utf-8 -*-
"""
Setting API Schemas - 设置请求/响应模型。
"""

from pydantic import BaseModel, Field


class AgentToolPermissionItem(BaseModel):
    """Agent 工具权限设置项。"""

    tool_name: str = Field(..., description="工具名称")
    mode: str = Field(..., description="权限模式：allow / ask / deny")


class AgentSettingsLockResponse(BaseModel):
    """Agent 会话是否正在锁定相关设置。"""

    is_locked: bool = Field(..., description="是否存在未结束的 Agent 或子智能体会话")


class AuditDetailsStorageResponse(BaseModel):
    """LLM 调用详情的存储概览。"""

    detail_records_count: int = Field(description="包含详情的调用记录数")
    detail_bytes: int = Field(description="详情字段 UTF-8 字节数估算")


class ClearAuditDetailsResponse(BaseModel):
    """清空 LLM 调用详情的结果。"""

    cleared_records_count: int = Field(description="已清空详情的调用记录数")
    cleared_detail_bytes: int = Field(description="已清空详情字段的 UTF-8 字节数估算")


class SettingsResponse(BaseModel):
    """设置响应。"""

    language: str = Field(default="zh-CN", description="语言")
    theme: str = Field(default="light", description="主题")
    font_family: str = Field(default="system-ui", description="字体")
    code_font_family: str = Field(default="ui-monospace", description="代码字体")
    base_font_size: int = Field(default=14, description="基础字号（px）")
    editor_font_size: int = Field(default=16, description="编辑器字号（px）")
    default_model: str = Field(default="", description="默认模型 ID")
    light_model: str = Field(default="", description="轻量模型 ID")
    default_embedding_model: str = Field(default="", description="默认 Embedding 模型 ID")
    index_mode: str = Field(default="off", description="索引启用模式：off/all/selected")
    index_enabled_projects: list[str] = Field(
        default_factory=list, description="启用索引的项目 ID 列表（mode=selected 时生效）"
    )
    index_chunk_size: int = Field(default=800, description="索引分块大小")
    index_chunk_overlap: int = Field(default=100, description="索引分块重叠")
    index_auto_strategy: str = Field(
        default="off", description="自动索引策略：immediate/agent_decided/off"
    )
    index_rerank_enabled: bool = Field(
        default=False,
        description="是否启用检索 rerank 二次排序",
    )
    default_rerank_model: str = Field(default="", description="默认 Rerank 模型 ID")
    agent_bypass_tool_approval: bool = Field(
        default=False,
        description="是否全局放行 Agent 工具审批",
    )
    agent_tool_permissions: list[AgentToolPermissionItem] = Field(
        default_factory=list, description="Agent 工具权限设置"
    )
    audit_persist_details: bool = Field(default=False, description="是否持久化 LLM 调用详情")
    compress_system_prompts: bool = Field(
        default=False,
        description="是否将连续的 system 消息合并为一条",
    )
    telemetry_enabled: bool = Field(
        default=True,
        description="是否启用 PostHog 错误遥测",
    )
    editor_auto_indent: bool = Field(
        default=True,
        description="换行时若当前段落以两个全角空格开头，是否为下一段自动添加相同前缀",
    )
    editor_auto_convert_punctuation: bool = Field(
        default=False,
        description="输入半角标点符号时是否自动转换为全角",
    )
    editor_auto_pair_symbols: bool = Field(
        default=False,
        description="输入成对符号的左符号时是否自动补齐右符号",
    )
    editor_show_line_numbers: bool = Field(
        default=False,
        description="是否在章节编辑器中显示行号",
    )


class SettingsUpdateRequest(BaseModel):
    """设置更新请求。"""

    language: str | None = Field(default=None, description="语言")
    theme: str | None = Field(default=None, description="主题")
    font_family: str | None = Field(default=None, description="字体")
    code_font_family: str | None = Field(default=None, description="代码字体")
    base_font_size: int | None = Field(default=None, description="基础字号（px）")
    editor_font_size: int | None = Field(default=None, description="编辑器字号（px）")
    default_model: str | None = Field(default=None, description="默认模型 ID")
    light_model: str | None = Field(default=None, description="轻量模型 ID")
    default_embedding_model: str | None = Field(
        default=None,
        description="默认 Embedding 模型 ID",
    )
    index_mode: str | None = Field(default=None, description="索引启用模式")
    index_enabled_projects: list[str] | None = Field(
        default=None, description="启用索引的项目 ID 列表"
    )
    index_chunk_size: int | None = Field(default=None, description="索引分块大小")
    index_chunk_overlap: int | None = Field(default=None, description="索引分块重叠")
    index_auto_strategy: str | None = Field(default=None, description="自动索引策略")
    index_rerank_enabled: bool | None = Field(
        default=None,
        description="是否启用检索 rerank 二次排序",
    )
    default_rerank_model: str | None = Field(
        default=None,
        description="默认 Rerank 模型 ID",
    )
    agent_bypass_tool_approval: bool | None = Field(
        default=None,
        description="是否全局放行 Agent 工具审批",
    )
    agent_tool_permissions: list[AgentToolPermissionItem] | None = Field(
        default=None, description="Agent 工具权限设置"
    )
    audit_persist_details: bool | None = Field(
        default=None, description="是否持久化 LLM 调用详情"
    )
    compress_system_prompts: bool | None = Field(
        default=None,
        description="是否将连续的 system 消息合并为一条",
    )
    telemetry_enabled: bool | None = Field(
        default=None,
        description="是否启用 PostHog 错误遥测",
    )
    editor_auto_indent: bool | None = Field(
        default=None,
        description="换行时若当前段落以两个全角空格开头，是否为下一段自动添加相同前缀",
    )
    editor_auto_convert_punctuation: bool | None = Field(
        default=None,
        description="输入半角标点符号时是否自动转换为全角",
    )
    editor_auto_pair_symbols: bool | None = Field(
        default=None,
        description="输入成对符号的左符号时是否自动补齐右符号",
    )
    editor_show_line_numbers: bool | None = Field(
        default=None,
        description="是否在章节编辑器中显示行号",
    )


class WebSearchProviderField(BaseModel):
    """联网搜索 provider 的扩展字段定义。"""

    key: str = Field(..., description="扩展参数键（存入 extras）")
    field_type: str = Field(..., description="字段类型：text / select")
    required: bool = Field(default=False, description="是否必填")
    options: list[str] = Field(default_factory=list, description="select 类型的可选值")


class WebSearchProviderInfo(BaseModel):
    """联网搜索 provider 元数据。"""

    name: str = Field(..., description="provider 名称")
    requires_api_key: bool = Field(..., description="是否需要 API Key")
    fields: list[WebSearchProviderField] = Field(
        default_factory=list, description="扩展字段定义"
    )


class WebSearchSettingsResponse(BaseModel):
    """联网搜索设置响应（不含明文 API Key）。"""

    enabled: bool = Field(..., description="是否启用联网搜索")
    provider: str = Field(..., description="当前 provider 名称")
    has_api_keys: dict[str, bool] = Field(
        default_factory=dict, description="各 provider 是否已配置 API Key"
    )
    max_results: int = Field(..., description="搜索结果数量限制")
    domain_filters: list[str] = Field(default_factory=list, description="域名过滤列表")
    extras: dict[str, str] = Field(default_factory=dict, description="扩展参数")


class WebSearchSettingsUpdateRequest(BaseModel):
    """联网搜索设置更新请求。"""

    enabled: bool | None = Field(default=None, description="是否启用联网搜索")
    provider: str | None = Field(default=None, description="provider 名称")
    api_key: str | None = Field(
        default=None,
        description="当前 provider 的 API Key：不传保持不变；传空字符串清除；传非空更新",
    )
    extras: dict[str, str] | None = Field(
        default=None, description="扩展参数（整体替换，不传保持不变）"
    )
    max_results: int | None = Field(
        default=None, ge=1, le=20, description="搜索结果数量限制（1-20）"
    )
    domain_filters: list[str] | None = Field(
        default=None, description="需要从搜索结果中排除的域名列表"
    )
