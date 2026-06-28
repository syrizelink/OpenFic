# -*- coding: utf-8 -*-
"""
WorldInfo API Schemas - 世界书请求/响应模型。
"""

from datetime import datetime

from pydantic import BaseModel, Field


# ============== 世界书 Schemas ==============


class WorldInfoCreate(BaseModel):
    """创建世界书请求。"""

    name: str = Field(min_length=1, max_length=200, description="世界书名称")
    project_id: str | None = Field(default=None, description="关联的项目 ID（可选）")
    description: str = Field(default="", description="世界书描述")


class WorldInfoUpdate(BaseModel):
    """更新世界书请求。"""

    name: str | None = Field(
        default=None, min_length=1, max_length=200, description="世界书名称"
    )
    project_id: str | None = Field(default=None, description="新的关联项目 ID")
    unbind_project: bool = Field(default=False, description="是否解除项目绑定")
    description: str | None = Field(default=None, description="世界书描述")


class WorldInfoResponse(BaseModel):
    """世界书响应。"""

    id: str = Field(description="世界书 ID")
    project_id: str | None = Field(description="关联的项目 ID，可为空")
    name: str = Field(description="世界书名称")
    description: str = Field(description="世界书描述")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

    model_config = {"from_attributes": True}


class WorldInfoListResponse(BaseModel):
    """世界书列表响应。"""

    items: list[WorldInfoResponse] = Field(description="世界书列表")
    total: int = Field(description="总数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页数量")


# ============== 世界书条目 Schemas ==============


class WorldInfoEntryCreate(BaseModel):
    """创建世界书条目请求。"""

    name: str = Field(min_length=1, max_length=200, description="条目名称")
    content: str = Field(default="", description="条目内容")
    token_count: int = Field(default=0, ge=0, description="Token 数量")
    is_enabled: bool = Field(default=True, description="开关状态")


class WorldInfoEntryUpdate(BaseModel):
    """更新世界书条目请求。"""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = None
    token_count: int | None = Field(default=None, ge=0)
    is_enabled: bool | None = None


class WorldInfoEntryMoveRequest(BaseModel):
    """移动世界书条目请求。"""

    new_order: int = Field(ge=1, description="新排序位置")


class WorldInfoEntryReorderRequest(BaseModel):
    """批量重新排序世界书条目请求。"""

    orders: dict[str, int] = Field(description="条目ID到新排序位置的映射")


class WorldInfoEntryBatchToggleRequest(BaseModel):
    """批量切换条目开关请求。"""

    entry_ids: list[str] = Field(min_length=1, description="要切换的条目 ID 列表")
    is_enabled: bool = Field(description="目标开关状态")


class WorldInfoEntryBatchDeleteRequest(BaseModel):
    """批量删除条目请求。"""

    entry_ids: list[str] = Field(min_length=1, description="要删除的条目 ID 列表")


class WorldInfoEntryBatchToggleResponse(BaseModel):
    """批量切换条目开关响应。"""

    updated_count: int = Field(description="已更新的条目数量")


class WorldInfoEntryBatchDeleteResponse(BaseModel):
    """批量删除条目响应。"""

    deleted_count: int = Field(description="已删除的条目数量")


class WorldInfoEntryResponse(BaseModel):
    """世界书条目响应。"""

    id: str = Field(description="条目 ID")
    world_info_id: str = Field(description="所属世界书 ID")
    uid: int = Field(description="用户可见序列号")
    name: str = Field(description="条目名称")
    order: int = Field(description="排序序号")
    content: str = Field(description="条目内容")
    token_count: int = Field(description="Token 数量")
    is_enabled: bool = Field(description="开关状态")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

    model_config = {"from_attributes": True}


class WorldInfoEntryBriefResponse(BaseModel):
    """世界书条目轻量响应（列表用，不含 content）。"""

    id: str = Field(description="条目 ID")
    world_info_id: str = Field(description="所属世界书 ID")
    uid: int = Field(description="用户可见序列号")
    name: str = Field(description="条目名称")
    order: int = Field(description="排序序号")
    token_count: int = Field(description="Token 数量")
    is_enabled: bool = Field(description="开关状态")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

    model_config = {"from_attributes": True}


class WorldInfoEntryBriefListResponse(BaseModel):
    """世界书条目轻量列表响应。"""

    items: list[WorldInfoEntryBriefResponse] = Field(description="条目列表")
    total: int = Field(description="总数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页数量")


class WorldInfoImportPreviewEntry(BaseModel):
    """世界书导入预览条目。"""

    uid: int = Field(description="原始条目 UID")
    name: str = Field(description="导入后的条目名称")
    content_preview: str = Field(description="内容预览")
    is_enabled: bool = Field(description="导入后的启用状态")


class WorldInfoImportPreviewResponse(BaseModel):
    """世界书导入预览响应。"""

    entry_count: int = Field(description="条目总数")
    enabled_count: int = Field(description="启用条目数")
    entries: list[WorldInfoImportPreviewEntry] = Field(description="预览条目列表")


class WorldInfoImportResponse(BaseModel):
    """世界书导入响应。"""

    world_info_id: str = Field(description="目标世界书 ID")
    imported_count: int = Field(description="成功导入的条目数")


# ============== 搜索 Schemas ==============


class WorldInfoEntrySearchMatch(BaseModel):
    """搜索匹配项。"""

    line_number: int = Field(description="匹配行号（从 1 开始）")
    line_text: str = Field(description="匹配行文本")


class WorldInfoEntrySearchResult(BaseModel):
    """单个条目的搜索结果。"""

    entry_id: str = Field(description="条目 ID")
    entry_name: str = Field(description="条目名称")
    uid: int = Field(description="条目 UID")
    matches: list[WorldInfoEntrySearchMatch] = Field(description="匹配项列表")


class WorldInfoEntrySearchResponse(BaseModel):
    """搜索响应。"""

    results: list[WorldInfoEntrySearchResult] = Field(description="搜索结果列表")
    total_entries: int = Field(description="匹配的条目总数")
    total_matches: int = Field(description="匹配项总数")
