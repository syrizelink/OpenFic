# -*- coding: utf-8 -*-
"""Character API Schemas - 角色请求/响应模型。"""

from datetime import datetime

from pydantic import BaseModel, Field


class CharacterResponse(BaseModel):
    """角色响应。"""

    id: str = Field(description="角色 ID")
    project_id: str = Field(description="所属项目 ID")
    name: str = Field(description="角色名称")
    description: str = Field(description="角色描述")
    image_url: str | None = Field(description="角色头像 URL")
    is_favorited: bool = Field(description="是否收藏")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")


class CharacterListItemResponse(BaseModel):
    """角色列表项响应。"""

    id: str = Field(description="角色 ID")
    project_id: str = Field(description="所属项目 ID")
    name: str = Field(description="角色名称")
    image_url: str | None = Field(description="角色头像 URL")
    token_count: int = Field(description="角色描述 Token 数")
    is_favorited: bool = Field(description="是否收藏")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")


class CharacterListResponse(BaseModel):
    """角色列表响应。"""

    items: list[CharacterListItemResponse] = Field(description="角色列表")
    total: int = Field(description="总数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页数量")


class CharacterSearchMatch(BaseModel):
    """角色搜索匹配项。"""

    line_number: int = Field(description="匹配行号（从 1 开始）")
    line_text: str = Field(description="匹配行文本")


class CharacterSearchResult(BaseModel):
    """单个角色的搜索结果。"""

    character_id: str = Field(description="角色 ID")
    character_name: str = Field(description="角色名称")
    matches: list[CharacterSearchMatch] = Field(description="匹配项列表")


class CharacterSearchResponse(BaseModel):
    """角色搜索响应。"""

    results: list[CharacterSearchResult] = Field(description="搜索结果列表")
    total_characters: int = Field(description="匹配的角色总数")
    total_matches: int = Field(description="匹配项总数")


class CharacterBatchFavoriteRequest(BaseModel):
    """批量收藏角色请求。"""

    character_ids: list[str] = Field(min_length=1, description="要更新的角色 ID 列表")
    is_favorited: bool = Field(description="目标收藏状态")


class CharacterBatchDeleteRequest(BaseModel):
    """批量删除角色请求。"""

    character_ids: list[str] = Field(min_length=1, description="要删除的角色 ID 列表")


class CharacterBatchFavoriteResponse(BaseModel):
    """批量收藏角色响应。"""

    updated_count: int = Field(description="已更新的角色数量")


class CharacterBatchDeleteResponse(BaseModel):
    """批量删除角色响应。"""

    deleted_count: int = Field(description="已删除的角色数量")
