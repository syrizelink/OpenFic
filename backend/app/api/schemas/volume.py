# -*- coding: utf-8 -*-
"""
Volume API Schemas - 卷请求/响应模型。
"""

from datetime import datetime

from pydantic import BaseModel, Field


class VolumeCreate(BaseModel):
    """创建卷请求。"""

    title: str = Field(min_length=1, max_length=200, description="卷名")
    description: str | None = Field(default=None, description="卷说明")


class VolumeUpdate(BaseModel):
    """更新卷请求。"""

    title: str | None = Field(
        default=None, min_length=1, max_length=200, description="卷名"
    )
    description: str | None = Field(default=None, description="卷说明")


class VolumeMove(BaseModel):
    """移动卷请求。"""

    new_order: int = Field(ge=1, description="新的排序位置")


class VolumeResponse(BaseModel):
    """卷响应。"""

    id: str = Field(description="卷 ID")
    project_id: str = Field(description="所属项目 ID")
    title: str = Field(description="卷名")
    description: str | None = Field(description="卷说明")
    order: int = Field(description="项目内排序序号")
    chapter_count: int = Field(description="章节数")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="上次修改时间")

    model_config = {"from_attributes": True}
