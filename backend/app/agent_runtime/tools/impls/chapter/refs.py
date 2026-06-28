from collections.abc import Sequence
from typing import Any, Literal, Protocol, TypeVar

from pydantic import BaseModel, Field, field_validator

from app.agent_runtime.tools.errors import ToolExecutionError


class ChapterRef(BaseModel):
    type: Literal["order", "title"] = Field(
        description="章节定位方式：order 表示卷内序号，title 表示章节标题",
    )
    value: int | str = Field(
        description="与 type 对应的章节定位值；order 时传整数，title 时传精确标题",
    )

    @field_validator("value", mode="before")
    @classmethod
    def coerce_value(cls, v: Any, info: Any) -> int | str:
        if info.data.get("type") == "order":
            return int(v)
        return str(v)


class VolumeRef(BaseModel):
    type: Literal["order", "title"] = Field(
        description="卷定位方式：order 表示卷序号，title 表示卷标题",
    )
    value: int | str = Field(
        description="与 type 对应的卷定位值；order 时传整数，title 时传精确标题",
    )

    @field_validator("value", mode="before")
    @classmethod
    def coerce_value(cls, v: Any, info: Any) -> int | str:
        if info.data.get("type") == "order":
            return int(v)
        return str(v)


class _OrderedTitled(Protocol):
    order: int
    title: str


_TOrderedTitled = TypeVar("_TOrderedTitled", bound=_OrderedTitled)


def resolve_volume_from_list(
    volumes: Sequence[_TOrderedTitled],
    ref: VolumeRef,
) -> _TOrderedTitled:
    if ref.type == "order":
        match = next((volume for volume in volumes if volume.order == ref.value), None)
    else:
        match = next((volume for volume in volumes if volume.title == ref.value), None)
    if match is None:
        raise ToolExecutionError(f"未找到卷: {ref.type}={ref.value}")
    return match


def resolve_chapter_from_list(
    chapters: Sequence[_TOrderedTitled],
    ref: ChapterRef,
) -> _TOrderedTitled:
    if ref.type == "order":
        match = next((chapter for chapter in chapters if chapter.order == ref.value), None)
    else:
        match = next((chapter for chapter in chapters if chapter.title == ref.value), None)
    if match is None:
        raise ToolExecutionError(f"未找到章节: {ref.type}={ref.value}")
    return match
