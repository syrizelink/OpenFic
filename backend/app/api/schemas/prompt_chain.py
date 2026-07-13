# -*- coding: utf-8 -*-
"""
PromptChain API Schemas - 提示词链请求/响应模型。
"""

from datetime import datetime

from pydantic import BaseModel, Field


class PromptEntryData(BaseModel):
    """提示词条目数据。"""

    id: str | None = Field(default=None, description="条目ID（可选）")
    uid: str | None = Field(default=None, description="跨版本追踪标识符（可选）")
    name: str = Field(min_length=1, max_length=200, description="条目名称")
    role: str = Field(description="角色类型（system/user/assistant）")
    content: str = Field(description="提示词内容")
    order_index: int = Field(ge=0, description="排序索引")
    is_enabled: bool = Field(default=True, description="是否启用")
    token_count: int = Field(ge=0, description="Token计数")


class PromptChainVersionResponse(BaseModel):
    """提示词链版本响应。"""

    id: str = Field(description="版本ID")
    prompt_id: str = Field(description="提示词唯一标识")
    version_hash: str = Field(description="版本短hash")
    version_number: int = Field(description="语义版本号")
    parent_version_id: str | None = Field(description="父版本ID")
    is_active: bool = Field(description="是否在当前活跃分支上")
    note: str | None = Field(description="版本备注")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}


class PromptEntryResponse(BaseModel):
    """提示词条目响应。"""

    id: str = Field(description="条目ID")
    uid: str = Field(description="跨版本追踪标识符")
    version_id: str = Field(description="所属版本ID")
    name: str = Field(description="条目名称")
    role: str = Field(description="角色类型")
    content: str = Field(description="提示词内容")
    order_index: int = Field(description="排序索引")
    is_enabled: bool = Field(description="是否启用")
    token_count: int = Field(description="Token计数")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

    model_config = {"from_attributes": True}


class PromptEntrySearchMatch(BaseModel):
    """提示词条目中的单行搜索命中。"""

    line_number: int = Field(description="行号，条目名称使用 0")
    line_text: str = Field(description="命中的原始文本")


class PromptEntrySearchResult(BaseModel):
    """单个提示词条目的搜索结果。"""

    entry_id: str = Field(description="条目 ID")
    entry_name: str = Field(description="条目名称")
    role: str = Field(description="角色类型")
    matches: list[PromptEntrySearchMatch] = Field(description="命中行")


class PromptEntrySearchResponse(BaseModel):
    """提示词版本内条目搜索响应。"""

    results: list[PromptEntrySearchResult] = Field(default_factory=list, description="搜索结果")
    total_entries: int = Field(ge=0, description="命中的条目数")
    total_matches: int = Field(ge=0, description="命中的行数")


class VersionWithEntriesResponse(BaseModel):
    """版本及其条目响应。"""

    version: PromptChainVersionResponse = Field(description="版本信息")
    entries: list[PromptEntryResponse] = Field(description="条目列表")


class CreateVersionRequest(BaseModel):
    """创建新版本请求。"""

    parent_version_id: str = Field(description="父版本ID")
    entries: list[PromptEntryData] = Field(description="条目列表")
    note: str | None = Field(default=None, max_length=500, description="版本备注")


class UpdateEntryRequest(BaseModel):
    """更新条目请求。"""

    name: str | None = Field(default=None, min_length=1, max_length=200, description="条目名称")
    role: str | None = Field(default=None, description="角色类型")
    content: str | None = Field(default=None, description="提示词内容")
    order_index: int | None = Field(default=None, ge=0, description="排序索引")
    is_enabled: bool | None = Field(default=None, description="是否启用")
    token_count: int | None = Field(default=None, ge=0, description="Token计数")


class PromptMetadata(BaseModel):
    """单个提示词元数据。"""

    id: str = Field(description="提示词唯一标识")
    label_key: str = Field(description="前端国际化标签键")
    label: str | None = Field(default=None, description="自定义显示名称")


class PromptCategoryMetadata(BaseModel):
    """提示词分类元数据。"""

    id: str = Field(description="分类标识")
    label_key: str = Field(description="前端国际化标签键")
    prompts: list[PromptMetadata] = Field(default_factory=list, description="提示词列表")


class PromptChainsMetadataResponse(BaseModel):
    """提示词链元数据响应。"""

    categories: list[PromptCategoryMetadata] = Field(default_factory=list, description="分类列表")


class CompiledEntryResponse(BaseModel):
    """编译后的条目响应。"""

    name: str = Field(description="条目名称")
    role: str = Field(description="角色类型")
    content: str = Field(description="编译后的内容")
    token_count: int = Field(ge=0, description="Token计数")


class CompileResponse(BaseModel):
    """编译响应。"""

    entries: list[CompiledEntryResponse] = Field(description="编译后的条目列表")
    total_tokens: int = Field(ge=0, description="总Token数")


class EntryDiffResponse(BaseModel):
    """条目差异响应。"""

    entry_id: str = Field(description="条目ID")
    change_type: str = Field(description="变化类型：added/deleted/modified")
    base_entry: PromptEntryResponse | None = Field(description="基准版本的条目")
    compare_entry: PromptEntryResponse | None = Field(description="对比版本的条目")


class VersionDiffResponse(BaseModel):
    """版本差异响应。"""

    base_version: PromptChainVersionResponse = Field(description="基准版本")
    compare_version: PromptChainVersionResponse = Field(description="对比版本")
    diffs: list[EntryDiffResponse] = Field(description="差异列表")
