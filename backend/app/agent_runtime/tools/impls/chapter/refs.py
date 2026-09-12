from collections.abc import Sequence
from typing import Any, Literal, Protocol, TypeVar

from pydantic import BaseModel, Field, field_validator

from app.agent_runtime.tools.errors import ToolExecutionError


class ChapterRef(BaseModel):
    type: Literal["order", "title"] = Field(
        description=(
            "Cara menentukan bab: order berarti nomor urut bab di dalam volume, "
            "title berarti judul bab"
        ),
    )
    value: int | str = Field(
        description=(
            "Nilai penentu bab yang sesuai dengan type; saat type adalah order, "
            "masukkan nomor urut berupa bilangan bulat, saat type adalah title, "
            "masukkan judul bab yang persis"
        ),
    )

    @field_validator("value", mode="before")
    @classmethod
    def coerce_value(cls, v: Any, info: Any) -> int | str:
        if info.data.get("type") == "order":
            return int(v)
        return str(v)


class VolumeRef(BaseModel):
    type: Literal["order", "title"] = Field(
        description=(
            "Cara menentukan volume: order berarti nomor urut volume, "
            "title berarti judul volume"
        ),
    )
    value: int | str = Field(
        description=(
            "Nilai penentu volume yang sesuai dengan type; saat type adalah order, "
            "masukkan nomor urut berupa bilangan bulat, saat type adalah title, "
            "masukkan judul volume yang persis"
        ),
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
        raise ToolExecutionError(f"Volume tidak ditemukan: {ref.type}={ref.value}")
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
        raise ToolExecutionError(f"Bab tidak ditemukan: {ref.type}={ref.value}")
    return match
