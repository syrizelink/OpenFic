# -*- coding: utf-8 -*-
"""
Note 工具引用解析。
"""

from collections.abc import Sequence

from pydantic import BaseModel, Field

from app.agent_runtime.tools.errors import ToolExecutionError
from app.storage.models.note import Note
from app.storage.models.note import NoteCategory


class NoteRef(BaseModel):
    id: str | None = Field(default=None, description="按 ID 定位")
    title: str | None = Field(default=None, description="按标题定位")
    path: str | None = Field(default=None, description="路径，如 /设定/角色/笔记标题")


class CategoryRef(BaseModel):
    id: str | None = Field(default=None, description="按 ID 定位")
    title: str | None = Field(default=None, description="按标题定位")
    path: str | None = Field(default=None, description="路径，如 /设定/角色")


def _resolve_category_by_path(
    categories: Sequence[NoteCategory],
    path: str,
) -> NoteCategory | None:
    segments = [s for s in path.strip("/").split("/") if s]
    if not segments:
        return None
    current_parent_id: str | None = None
    for segment in segments:
        match = next(
            (
                c
                for c in categories
                if c.parent_id == current_parent_id and c.title == segment
            ),
            None,
        )
        if match is None:
            return None
        current_parent_id = match.id
    return match


def resolve_note_from_list(
    notes: Sequence[Note],
    ref: NoteRef,
    *,
    categories: Sequence[NoteCategory] | None = None,
) -> Note:
    if ref.id is not None:
        match = next((n for n in notes if n.id == ref.id), None)
        if match is not None:
            return match
    if ref.path is not None and categories is not None:
        segments = [s for s in ref.path.strip("/").split("/") if s]
        if segments:
            note_title = segments[-1]
            if len(segments) == 1:
                category_id: str | None = None
            else:
                cat_path = "/".join(segments[:-1])
                cat = _resolve_category_by_path(categories, cat_path)
                if cat is None:
                    raise ToolExecutionError(f"路径中分类不存在: {cat_path}")
                category_id = cat.id
            match = next(
                (
                    n
                    for n in notes
                    if n.category_id == category_id and n.title == note_title
                ),
                None,
            )
            if match is not None:
                return match
    if ref.title is not None:
        match = next((n for n in notes if n.title == ref.title), None)
        if match is not None:
            return match
    raise ToolExecutionError(f"未找到笔记: id={ref.id}, title={ref.title}, path={ref.path}")


def resolve_category_from_list(
    categories: Sequence[NoteCategory], ref: CategoryRef
) -> NoteCategory:
    if ref.id is not None:
        match = next((c for c in categories if c.id == ref.id), None)
        if match is not None:
            return match
    if ref.path is not None:
        match = _resolve_category_by_path(categories, ref.path)
        if match is not None:
            return match
    if ref.title is not None:
        match = next((c for c in categories if c.title == ref.title), None)
        if match is not None:
            return match
    raise ToolExecutionError(f"未找到分类: id={ref.id}, title={ref.title}, path={ref.path}")


def generate_unique_title(base_title: str, existing_titles: set[str]) -> str:
    if base_title not in existing_titles:
        return base_title
    counter = 1
    while True:
        candidate = f"{base_title}({counter})"
        if candidate not in existing_titles:
            return candidate
        counter += 1
