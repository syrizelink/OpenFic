# -*- coding: utf-8 -*-
"""
Note API Schemas - 笔记请求/响应模型。
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class NoteCategoryCreate(BaseModel):
    parent_id: str | None = Field(default=None, description="父分类 ID")
    title: str = Field(min_length=1, max_length=200, description="分类标题")


class NoteCategoryUpdate(BaseModel):
    title: str | None = Field(
        default=None, min_length=1, max_length=200, description="分类标题"
    )


class NoteCreate(BaseModel):
    category_id: str | None = Field(default=None, description="所属分类 ID")
    title: str = Field(min_length=1, max_length=200, description="笔记标题")
    content: str = Field(default="", description="笔记内容")


class NoteUpdate(BaseModel):
    title: str | None = Field(
        default=None, min_length=1, max_length=200, description="笔记标题"
    )
    content: str | None = Field(default=None, description="笔记内容")


class NoteLockToggle(BaseModel):
    is_locked: bool = Field(description="是否锁定")


class NoteHiddenToggle(BaseModel):
    is_hidden: bool = Field(description="是否隐藏")


class NoteItemMove(BaseModel):
    kind: Literal["category", "note"] = Field(description="移动类型")
    item_id: str = Field(description="被移动的分类/笔记 ID")
    target_category_id: str | None = Field(default=None, description="目标分类 ID")


class NoteResponse(BaseModel):
    id: str = Field(description="笔记 ID")
    project_id: str = Field(description="所属项目 ID")
    category_id: str | None = Field(description="所属分类 ID")
    title: str = Field(description="笔记标题")
    content: str = Field(description="笔记内容")
    is_locked: bool = Field(description="是否锁定")
    is_hidden: bool = Field(description="是否隐藏")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="上次修改时间")

    model_config = {"from_attributes": True}


class NoteListItem(BaseModel):
    id: str = Field(description="笔记 ID")
    project_id: str = Field(description="所属项目 ID")
    category_id: str | None = Field(description="所属分类 ID")
    title: str = Field(description="笔记标题")
    is_locked: bool = Field(description="是否锁定")
    is_hidden: bool = Field(description="是否隐藏")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="上次修改时间")

    model_config = {"from_attributes": True}


class NoteCategoryResponse(BaseModel):
    id: str = Field(description="分类 ID")
    project_id: str = Field(description="所属项目 ID")
    parent_id: str | None = Field(description="父分类 ID")
    title: str = Field(description="分类标题")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="上次修改时间")

    model_config = {"from_attributes": True}


class NoteCategoryItem(BaseModel):
    id: str = Field(description="分类 ID")
    project_id: str = Field(description="所属项目 ID")
    parent_id: str | None = Field(description="父分类 ID")
    title: str = Field(description="分类标题")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="上次修改时间")
    categories: list["NoteCategoryItem"] = Field(description="子分类列表")
    notes: list[NoteListItem] = Field(description="分类下笔记列表")

    model_config = {"from_attributes": True}


class NoteTreeResponse(BaseModel):
    categories: list[NoteCategoryItem] = Field(description="分类树")
    root_notes: list[NoteListItem] = Field(description="根级笔记")
    total_notes: int = Field(description="笔记总数")


class NoteMoveResult(BaseModel):
    kind: Literal["category", "note"] = Field(description="移动类型")
    note: NoteResponse | None = Field(default=None, description="移动的笔记")
    category: NoteCategoryResponse | None = Field(
        default=None, description="移动的分类"
    )


NoteCategoryItem.model_rebuild()


class NoteSearchMatch(BaseModel):
    """笔记内容搜索匹配行。"""

    line_number: int = Field(description="匹配行号")
    line_text: str = Field(description="匹配行文本")


class NoteSearchResult(BaseModel):
    """笔记内容搜索结果。"""

    note_id: str = Field(description="笔记 ID")
    note_title: str = Field(description="笔记标题")
    category_path: str = Field(description="所属分类路径")
    matches: list[NoteSearchMatch] = Field(description="匹配行列表")


class NoteSearchResponse(BaseModel):
    """笔记内容搜索响应。"""

    results: list[NoteSearchResult] = Field(description="搜索结果列表")
    total_notes: int = Field(description="匹配笔记数")
    total_matches: int = Field(description="匹配行总数")
