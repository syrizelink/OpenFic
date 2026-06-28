# -*- coding: utf-8 -*-
"""
Project API Schemas - 项目请求/响应模型。
"""

from datetime import datetime

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    """创建项目请求。"""

    title: str = Field(min_length=1, max_length=200, description="项目标题")
    description: str | None = Field(default=None, description="项目简介")


class ProjectUpdate(BaseModel):
    """更新项目请求。"""

    title: str | None = Field(
        default=None, min_length=1, max_length=200, description="项目标题"
    )
    description: str | None = Field(default=None, description="项目简介")


class ProjectResponse(BaseModel):
    """项目响应。"""

    id: str = Field(description="项目 ID")
    title: str = Field(description="项目标题")
    description: str | None = Field(description="项目简介")
    word_count: int = Field(description="统计字数")
    chapter_count: int = Field(description="总章节数")
    cover_url: str | None = Field(description="封面 URL")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="上次修改时间")

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    """项目列表响应。"""

    items: list[ProjectResponse] = Field(description="项目列表")
    total: int = Field(description="总数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页数量")
