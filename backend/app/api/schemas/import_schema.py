# -*- coding: utf-8 -*-
"""
Import API Schemas - 导入请求/响应模型。
"""

from pydantic import BaseModel, Field


class PreviewChapter(BaseModel):
    """预览章节信息。"""

    title: str = Field(description="章节标题")
    word_count: int = Field(description="章节字数")
    content_preview: str = Field(description="内容预览（前 200 字）")


class ImportPreviewResponse(BaseModel):
    """导入预览响应。"""

    chapters: list[PreviewChapter] = Field(description="章节列表")
    total_word_count: int = Field(description="总字数")
    chapter_count: int = Field(description="章节数")
    detected_encoding: str = Field(description="检测到的编码")


class ImportConfirmRequest(BaseModel):
    """确认导入请求。"""

    title: str = Field(min_length=1, max_length=200, description="书名")
    description: str | None = Field(default=None, description="简介")


class ImportConfirmResponse(BaseModel):
    """确认导入响应。"""

    project_id: str = Field(description="创建的项目 ID")
    title: str = Field(description="书名")
    chapter_count: int = Field(description="导入的章节数")
    total_word_count: int = Field(description="总字数")
