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


class NoteSiblingRef(BaseModel):
    kind: Literal["category", "note"]
    item_id: str


class NoteItemReorder(BaseModel):
    kind: Literal["category", "note"]
    item_id: str
    target_category_id: str | None = None
    ordered_siblings: list[NoteSiblingRef] = Field(min_length=1)


class NoteResponse(BaseModel):
    id: str = Field(description="笔记 ID")
    project_id: str = Field(description="所属项目 ID")
    category_id: str | None = Field(description="所属分类 ID")
    title: str = Field(description="笔记标题")
    content: str = Field(description="笔记内容")
    is_locked: bool = Field(description="是否锁定")
    is_hidden: bool = Field(description="是否隐藏")
    order_index: int = Field(description="同级顺序")
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
    order_index: int = Field(description="同级顺序")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="上次修改时间")

    model_config = {"from_attributes": True}


class NoteCategoryResponse(BaseModel):
    id: str = Field(description="分类 ID")
    project_id: str = Field(description="所属项目 ID")
    parent_id: str | None = Field(description="父分类 ID")
    title: str = Field(description="分类标题")
    order_index: int = Field(description="同级顺序")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="上次修改时间")

    model_config = {"from_attributes": True}


class NoteCategoryItem(BaseModel):
    id: str = Field(description="分类 ID")
    project_id: str = Field(description="所属项目 ID")
    parent_id: str | None = Field(description="父分类 ID")
    title: str = Field(description="分类标题")
    order_index: int = Field(description="同级顺序")
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


class NoteImportPreviewResponse(BaseModel):
    """笔记导入预览响应。"""

    file_type: Literal["md", "zip"] = Field(description="导入文件类型")
    note_count: int = Field(description="Markdown 笔记数量")
    category_count: int = Field(description="分类数量")
    ignored_file_count: int = Field(description="忽略的非 Markdown 文件数量")


class NoteImportResponse(BaseModel):
    """笔记导入响应。"""

    file_type: Literal["md", "zip"] = Field(description="导入文件类型")
    imported_note_count: int = Field(description="导入的笔记数量")
    imported_category_count: int = Field(description="创建的分类数量")
    ignored_file_count: int = Field(description="忽略的非 Markdown 文件数量")


NoteConflictStrategy = Literal["rename", "overwrite", "skip"]


class ProjectNoteImportRequest(BaseModel):
    source_project_id: str
    selected_category_ids: list[str] = Field(default_factory=list)
    selected_note_ids: list[str] = Field(default_factory=list)
    default_conflict_strategy: NoteConflictStrategy = "rename"
    conflict_overrides: dict[str, NoteConflictStrategy] = Field(default_factory=dict)


class ProjectNoteImportAction(BaseModel):
    source_note_id: str
    source_path: str
    target_title: str
    action: Literal["create", "rename", "overwrite", "skip"]


class ProjectNoteImportPreviewResponse(BaseModel):
    categories: list[NoteCategoryItem]
    root_notes: list[NoteListItem]
    actions: list[ProjectNoteImportAction]
    create_category_count: int
    merge_category_count: int
    create_note_count: int
    overwrite_note_count: int
    skip_note_count: int


class ProjectNoteImportResponse(BaseModel):
    created_category_count: int
    merged_category_count: int
    created_note_count: int
    renamed_note_count: int
    overwritten_note_count: int
    skipped_note_count: int
