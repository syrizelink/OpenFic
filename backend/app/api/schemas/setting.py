# -*- coding: utf-8 -*-
"""
Setting API Schemas - 设置请求/响应模型。
"""

from pydantic import BaseModel, Field


class AgentToolPermissionItem(BaseModel):
    """Agent 工具权限设置项。"""

    tool_name: str = Field(..., description="工具名称")
    mode: str = Field(..., description="权限模式：allow / ask / deny")


class SettingsResponse(BaseModel):
    """设置响应。"""

    language: str = Field(default="zh-CN", description="语言")
    theme: str = Field(default="light", description="主题")
    font_family: str = Field(default="SourceHanSerifCN-VF", description="字体")
    code_font_family: str = Field(default="JetBrainsMapleMono", description="代码字体")
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


class SettingsUpdateRequest(BaseModel):
    """设置更新请求。"""

    language: str | None = Field(default=None, description="语言")
    theme: str | None = Field(default=None, description="主题")
    font_family: str | None = Field(default=None, description="字体")
    code_font_family: str | None = Field(default=None, description="代码字体")
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
