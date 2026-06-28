from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.tools.impls.chapter.refs import (
    ChapterRef,
    VolumeRef,
    resolve_chapter_from_list,
    resolve_volume_from_list,
)
from app.storage.models.chapter import Chapter
from app.storage.models.volume import Volume
from app.storage.repos import chapter_repo, volume_repo


@dataclass(frozen=True)
class ChapterPreviewData:
    id: str | None
    project_id: str
    volume_id: str
    title: str
    content: str
    order: int | None = None
    word_count: int | None = None


def chapter_preview_from_object(chapter: object | None) -> ChapterPreviewData | None:
    if chapter is None:
        return None
    return ChapterPreviewData(
        id=getattr(chapter, "id", None),
        project_id=str(getattr(chapter, "project_id", "") or ""),
        volume_id=str(getattr(chapter, "volume_id", "") or ""),
        title=str(getattr(chapter, "title", "") or ""),
        content=str(getattr(chapter, "content", "") or ""),
        order=_as_int(getattr(chapter, "order", None)),
        word_count=_as_int(getattr(chapter, "word_count", None)),
    )


def serialize_preview_chapter(chapter: ChapterPreviewData | None) -> dict[str, Any] | None:
    if chapter is None:
        return None
    payload: dict[str, Any] = {
        "title": chapter.title,
        "content": chapter.content,
    }
    if chapter.id:
        payload["id"] = chapter.id
        payload["chapter_id"] = chapter.id
    if chapter.project_id:
        payload["project_id"] = chapter.project_id
    if chapter.volume_id:
        payload["volume_id"] = chapter.volume_id
    if chapter.order is not None:
        payload["order"] = chapter.order
    if chapter.word_count is not None:
        payload["word_count"] = chapter.word_count
    return payload


def build_chapter_diff_preview(
    before: ChapterPreviewData | None,
    after: ChapterPreviewData | None,
) -> dict[str, Any]:
    operation = "create" if before is None else "update"
    sections: list[dict[str, Any]] = []

    if before is None or after is None or before.title != after.title:
        sections.append({
            "label": "标题",
            "lines": _build_diff_lines(
                before.title if before else "",
                after.title if after else "",
            ),
        })

    if before is None or after is None or before.content != after.content:
        sections.append({
            "label": "内容",
            "lines": _build_diff_lines(
                before.content if before else "",
                after.content if after else "",
            ),
        })

    payload: dict[str, Any] = {
        "operation": operation,
        "sections": sections,
    }
    chapter = after or before
    if chapter is not None:
        if chapter.id:
            payload["chapter_id"] = chapter.id
        payload["chapter_title"] = chapter.title
        if chapter.order is not None:
            payload["order"] = chapter.order
    return payload


def build_tool_result_preview(
    before: ChapterPreviewData | None,
    after: ChapterPreviewData | None,
) -> dict[str, Any]:
    preview_data = {
        "chapter": serialize_preview_chapter(after or before),
        "chapter_diff": build_chapter_diff_preview(before, after),
    }
    return {
        "type": "preview",
        "success": True,
        "reason": "approval_preview",
        "message": "章节修改待审批",
        "data": preview_data,
    }


async def build_write_chapter_tool_result_preview(
    session: AsyncSession,
    project_id: str,
    *,
    volume_ref: dict,
    title: str,
    content: str,
    chapter_ref: dict | None = None,
    word_count: int | None = None,
) -> dict[str, Any]:
    volume = await _resolve_volume(session, project_id, volume_ref)
    order = await _resolve_write_order(session, volume.id, chapter_ref)
    after = ChapterPreviewData(
        id=None,
        project_id=project_id,
        volume_id=volume.id,
        title=title,
        content=content,
        order=order,
        word_count=word_count,
    )
    return build_tool_result_preview(None, after)


async def build_edit_chapter_tool_result_preview(
    session: AsyncSession,
    project_id: str,
    *,
    volume_ref: dict,
    chapter_ref: dict,
    new_title: str | None = None,
    old_content: str | None = None,
    new_content: str | None = None,
    replace_all: bool = False,
) -> dict[str, Any] | None:
    volume = await _resolve_volume(session, project_id, volume_ref)
    match = await _resolve_chapter(session, volume.id, chapter_ref)
    if match is None:
        return None

    before = chapter_preview_from_object(match)
    if before is None:
        return None

    updated_title = new_title if new_title is not None else before.title
    updated_content = before.content
    if old_content is not None and new_content is not None:
        if old_content not in updated_content:
            return None
        if replace_all:
            updated_content = updated_content.replace(old_content, new_content)
        else:
            updated_content = updated_content.replace(old_content, new_content, 1)

    after = ChapterPreviewData(
        id=before.id,
        project_id=before.project_id,
        volume_id=before.volume_id,
        title=updated_title,
        content=updated_content,
        order=before.order,
        word_count=before.word_count,
    )
    return build_tool_result_preview(before, after)


def _build_diff_lines(before: str, after: str) -> list[dict[str, Any]]:
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    matcher = SequenceMatcher(a=before_lines, b=after_lines, autojunk=False)
    lines: list[dict[str, Any]] = []
    before_line_number = 1
    after_line_number = 1

    for tag, before_start, before_end, after_start, after_end in matcher.get_opcodes():
        if tag == "equal":
            before_line_number += before_end - before_start
            after_line_number += after_end - after_start
            continue

        if tag in {"delete", "replace"}:
            for line in before_lines[before_start:before_end]:
                lines.append({
                    "type": "removed",
                    "before_line_number": before_line_number,
                    "after_line_number": None,
                    "text": line,
                })
                before_line_number += 1

        if tag in {"insert", "replace"}:
            for line in after_lines[after_start:after_end]:
                lines.append({
                    "type": "added",
                    "before_line_number": None,
                    "after_line_number": after_line_number,
                    "text": line,
                })
                after_line_number += 1

    return lines


async def _resolve_write_order(
    session: AsyncSession,
    volume_id: str,
    chapter_ref: dict | None,
) -> int:
    max_order = await chapter_repo.get_max_order(session, volume_id)
    if chapter_ref is None:
        return max_order + 1

    chapters = await chapter_repo.list_by_volume(session, volume_id)
    match = resolve_chapter_from_list(chapters, ChapterRef.model_validate(chapter_ref))
    return int(match.order)


async def _resolve_chapter(
    session: AsyncSession,
    volume_id: str,
    chapter_ref: dict,
) -> Chapter | None:
    chapters = await chapter_repo.list_by_volume(session, volume_id)
    ref_type = str(chapter_ref.get("type") or "")
    ref_value = chapter_ref.get("value")
    if ref_type == "order":
        order = _as_int(ref_value)
        if order is None:
            return None
        return next((chapter for chapter in chapters if chapter.order == order), None)
    if ref_type == "title":
        title = str(ref_value or "")
        return next((chapter for chapter in chapters if chapter.title == title), None)
    return None


async def _resolve_volume(
    session: AsyncSession,
    project_id: str,
    volume_ref: dict,
) -> Volume:
    volumes = await volume_repo.list_by_project(session, project_id)
    return resolve_volume_from_list(volumes, VolumeRef.model_validate(volume_ref))


def _as_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(cast(Any, value))
    except (TypeError, ValueError):
        return None
