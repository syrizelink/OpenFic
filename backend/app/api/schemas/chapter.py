# -*- coding: utf-8 -*-
"""
Chapter API Schemas - 章节请求/响应模型。
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ChapterCreate(BaseModel):
    """创建章节请求。"""

    volume_id: str = Field(description="所属卷 ID")
    title: str = Field(min_length=1, max_length=200, description="章节标题")
    content: str = Field(default="", description="章节内容")
    word_count: int | None = Field(
        default=None, ge=0, description="章节字数（前端计算）"
    )


class ChapterUpdate(BaseModel):
    """更新章节请求。"""

    title: str | None = Field(
        default=None, min_length=1, max_length=200, description="章节标题"
    )
    content: str | None = Field(default=None, description="章节内容")
    word_count: int | None = Field(
        default=None, ge=0, description="章节字数（前端计算）"
    )


class ChapterReorder(BaseModel):
    """批量重排章节请求。"""

    volume_id: str = Field(description="卷 ID")
    chapter_ids: list[str] = Field(description="按新顺序排列的章节 ID 列表")


class ChapterMoveToVolume(BaseModel):
    """跨卷移动章节请求。"""

    volume_id: str = Field(description="目标卷 ID")


class ChapterResponse(BaseModel):
    """章节响应（完整版，包含正文）。"""

    id: str = Field(description="章节 ID")
    project_id: str = Field(description="所属项目 ID")
    volume_id: str = Field(description="所属卷 ID")
    title: str = Field(description="章节标题")
    content: str = Field(description="章节内容")
    word_count: int = Field(description="章节字数")
    order: int = Field(description="排序序号")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="上次修改时间")

    model_config = {"from_attributes": True}


class ChapterListItem(BaseModel):
    """章节列表项（精简版，不含正文，用于列表展示）。"""

    id: str = Field(description="章节 ID")
    project_id: str = Field(description="所属项目 ID")
    volume_id: str = Field(description="所属卷 ID")
    title: str = Field(description="章节标题")
    word_count: int = Field(description="章节字数")
    order: int = Field(description="排序序号")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="上次修改时间")

    model_config = {"from_attributes": True}


class VolumeTreeItem(BaseModel):
    """卷-章树中的卷节点。"""

    id: str = Field(description="卷 ID")
    project_id: str = Field(description="所属项目 ID")
    title: str = Field(description="卷名")
    description: str | None = Field(description="卷说明")
    order: int = Field(description="项目内排序序号")
    chapter_count: int = Field(description="章节数")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="上次修改时间")
    chapters: list[ChapterListItem] = Field(description="卷内章节列表")

    model_config = {"from_attributes": True}


class VolumeTreeResponse(BaseModel):
    """卷-章树响应。"""

    volumes: list[VolumeTreeItem] = Field(description="卷列表")
    total_chapters: int = Field(description="章节总数")


class MentionCandidateItem(BaseModel):
    """对话 mention 候选项。"""

    kind: Literal[
        "volume",
        "chapter",
        "note",
        "note_category",
        "world_info_entry",
        "character",
    ] = Field(description="候选类型")
    id: str = Field(description="卷或章节 ID")
    title: str = Field(description="候选标题")
    label: str = Field(description="插入 mention 时使用的标签")
    description: str | None = Field(default=None, description="附加说明")


class MentionCandidateSearchResponse(BaseModel):
    """mention 候选检索结果。"""

    items: list[MentionCandidateItem] = Field(description="匹配到的候选项")


class ChapterSearchMatch(BaseModel):
    """章节内容搜索匹配行。"""

    line_number: int = Field(description="匹配行号")
    line_text: str = Field(description="匹配行文本")


class ChapterSearchResult(BaseModel):
    """章节内容搜索结果。"""

    chapter_id: str = Field(description="章节 ID")
    chapter_title: str = Field(description="章节标题")
    volume_title: str = Field(description="所属卷标题")
    matches: list[ChapterSearchMatch] = Field(description="匹配行列表")


class ChapterSearchResponse(BaseModel):
    """章节内容搜索响应。"""

    results: list[ChapterSearchResult] = Field(description="搜索结果列表")
    total_chapters: int = Field(description="匹配章节数")
    total_matches: int = Field(description="匹配行总数")
