# -*- coding: utf-8 -*-
"""
Context Builder - 上下文构建核心算法。
"""

import json
from dataclasses import dataclass

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.chapter.sequence import global_order_index
from app.storage.models.chapter import Chapter
from app.storage.models.chapter_summary import ChapterSummary
from app.storage.repos import chapter_repo, chapter_summary_repo, volume_repo


@dataclass
class ContextPart:
    """上下文部分。"""

    content: str
    token_count: int
    chapter_range: tuple[int, int]


@dataclass
class BuiltContext:
    """构建完成的上下文。"""

    latest_field: ContextPart
    near_field: ContextPart
    mid_field: ContextPart
    far_field: ContextPart
    chapter_list_field: ContextPart


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 2)


def _to_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _empty_part() -> ContextPart:
    return ContextPart(content="[]", token_count=1, chapter_range=(0, 0))


async def build_context(
    session: AsyncSession,
    project_id: str,
    chapter_id: str,
) -> BuiltContext:
    """
    构建完整上下文（以 chapter_id 为锚点，基于全局阅读序位）。

    算法：
    1. latest：当前章节原文
    2. near：当前章节之前 9 章原文
    3. middle：near 之前 10 章章节摘要
    4. far：middle 之前的远期区间摘要
    5. chapter_list：最新 50 章目录
    """
    all_chapters = await chapter_repo.list_by_project(session, project_id)
    volumes = await volume_repo.list_by_project(session, project_id)
    order_map = global_order_index(all_chapters, volumes)
    chapter_by_global_order = {order_map[ch.id]: ch for ch in all_chapters}

    current_chapter = next((ch for ch in all_chapters if ch.id == chapter_id), None)
    if current_chapter is None:
        empty = _empty_part()
        logger.warning(f"上下文构建: 章节不存在 chapter_id={chapter_id}")
        return BuiltContext(
            latest_field=empty,
            near_field=empty,
            mid_field=empty,
            far_field=empty,
            chapter_list_field=_build_chapter_list_field(all_chapters, order_map),
        )

    current_global_order = order_map[current_chapter.id]

    latest_field = _build_latest_field(current_chapter, current_global_order)

    near_field = _build_near_field(
        chapter_by_global_order=chapter_by_global_order,
        current_global_order=current_global_order,
        chapter_count=9,
    )

    mid_field = await _build_mid_field(
        session=session,
        project_id=project_id,
        chapters=all_chapters,
        order_map=order_map,
        start_order=current_global_order - 19,
        end_order=current_global_order - 10,
    )

    far_field = await _build_far_field(
        session=session,
        project_id=project_id,
        max_end_order=current_global_order - 20,
    )

    chapter_list_field = _build_chapter_list_field(all_chapters, order_map)

    logger.info(
        f"上下文构建完成: project_id={project_id}, "
        f"latest={latest_field.chapter_range}, "
        f"near={near_field.chapter_range}, "
        f"mid={mid_field.chapter_range}, "
        f"far={far_field.chapter_range}"
    )

    return BuiltContext(
        latest_field=latest_field,
        near_field=near_field,
        mid_field=mid_field,
        far_field=far_field,
        chapter_list_field=chapter_list_field,
    )


def _build_latest_field(
    chapter: Chapter,
    global_order: int,
) -> ContextPart:
    content = _to_json(
        {
            "order": global_order,
            "title": chapter.title,
            "content": chapter.content,
            "word_count": chapter.word_count,
        }
    )
    return ContextPart(
        content=content,
        token_count=_estimate_tokens(content),
        chapter_range=(global_order, global_order),
    )


def _build_near_field(
    chapter_by_global_order: dict[int, Chapter],
    current_global_order: int,
    chapter_count: int,
) -> ContextPart:
    selected_orders: list[int] = []
    for i in range(1, chapter_count + 1):
        target_order = current_global_order - i
        if target_order in chapter_by_global_order:
            selected_orders.append(target_order)

    if not selected_orders:
        return _empty_part()

    selected_orders.sort()

    chapters = []
    for order in selected_orders:
        chapter = chapter_by_global_order[order]
        chapters.append(
            {
                "order": order,
                "title": chapter.title,
                "content": chapter.content,
                "word_count": chapter.word_count,
            }
        )

    content = _to_json(chapters)
    return ContextPart(
        content=content,
        token_count=_estimate_tokens(content),
        chapter_range=(min(selected_orders), max(selected_orders)),
    )


async def _build_mid_field(
    session: AsyncSession,
    project_id: str,
    chapters: list[Chapter],
    order_map: dict[str, int],
    start_order: int,
    end_order: int,
) -> ContextPart:
    if end_order < 1:
        return _empty_part()
    start_order = max(1, start_order)
    if end_order < start_order:
        return _empty_part()

    target_chapters = [
        ch for ch in chapters if start_order <= order_map.get(ch.id, -1) <= end_order
    ]

    if not target_chapters:
        return _empty_part()

    target_chapters.sort(key=lambda ch: order_map[ch.id])

    chapter_ids = [ch.id for ch in target_chapters]
    summaries = await chapter_summary_repo.list_chapter_summaries_by_chapter_ids(
        session, chapter_ids, ready_only=True
    )
    summary_map = {s.chapter_id: s for s in summaries}

    selected: list[tuple[Chapter, ChapterSummary]] = []
    total_tokens = 0

    for chapter in target_chapters:
        summary = summary_map.get(chapter.id)
        if not summary:
            continue
        summary_tokens = summary.token_count or _estimate_tokens(summary.summary)
        selected.append((chapter, summary))
        total_tokens += summary_tokens

    if not selected:
        return _empty_part()

    selected.sort(key=lambda x: order_map[x[0].id])

    summary_payloads: list[dict[str, object]] = []
    for chapter, summary in selected:
        summary_payloads.append(
            {
                "order": order_map[chapter.id],
                "title": chapter.title,
                "summary": summary.summary,
            }
        )

    content = _to_json(summary_payloads)
    return ContextPart(
        content=content,
        token_count=total_tokens,
        chapter_range=(
            order_map[selected[0][0].id],
            order_map[selected[-1][0].id],
        ),
    )


async def _build_far_field(
    session: AsyncSession,
    project_id: str,
    max_end_order: int,
) -> ContextPart:
    if max_end_order < 1:
        return _empty_part()

    long_term_summaries = await chapter_summary_repo.list_long_term_summaries_by_project(
        session, project_id, ready_only=True
    )

    if not long_term_summaries:
        return _empty_part()

    long_term_summaries.sort(key=lambda item: item.start_order or 0)

    summaries = []
    total_tokens = 0
    for item in long_term_summaries:
        if (item.end_order or 0) > max_end_order:
            continue
        total_tokens += item.token_count or _estimate_tokens(item.summary)
        summaries.append(
            {
                "start_order": item.start_order,
                "end_order": item.end_order,
                "summary": item.summary,
            }
        )

    if not summaries:
        return _empty_part()

    content = _to_json(summaries)

    first_start = long_term_summaries[0].start_order or 0
    last_end = max_end_order
    return ContextPart(
        content=content,
        token_count=total_tokens,
        chapter_range=(first_start, last_end),
    )


def _build_chapter_list_field(
    chapters: list[Chapter],
    order_map: dict[str, int],
) -> ContextPart:
    ordered = sorted(chapters, key=lambda ch: order_map.get(ch.id, float("inf")))
    latest_chapters = ordered[-50:]
    content = _to_json(
        [
            {
                "order": order_map[chapter.id],
                "title": chapter.title,
            }
            for chapter in latest_chapters
        ]
    )
    if not latest_chapters:
        return ContextPart(content=content, token_count=1, chapter_range=(0, 0))
    return ContextPart(
        content=content,
        token_count=_estimate_tokens(content),
        chapter_range=(
            order_map[latest_chapters[0].id],
            order_map[latest_chapters[-1].id],
        ),
    )
