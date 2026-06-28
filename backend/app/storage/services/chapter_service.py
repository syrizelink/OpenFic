# -*- coding: utf-8 -*-
"""
Chapter Service - 章节业务逻辑层。
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.storage.models.chapter import Chapter
from app.storage.models.volume import Volume
from app.storage.repos import (
    chapter_repo,
    chapter_summary_repo,
    project_repo,
    volume_repo,
)
from app.storage.services import writing_activity_service


@dataclass
class VolumeChapterGroup:
    """卷与其章节列表。"""

    volume: Volume
    chapters: list[Chapter]


@dataclass
class VolumeTreeResult:
    """卷-章树结果。"""

    volumes: list[VolumeChapterGroup]
    total_chapters: int


@dataclass(frozen=True)
class MentionCandidate:
    """对话 mention 候选项。"""

    kind: Literal["volume", "chapter"]
    id: str
    title: str
    label: str
    description: str | None = None


def _count_words(text: str) -> int:
    """
    计算中英文混合文本的字数。

    中文按字符计数，英文按单词计数。

    Args:
        text: 待计算的文本。

    Returns:
        字数。
    """
    if not text:
        return 0

    # 匹配中文字符
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
    chinese_count = len(chinese_chars)

    # 移除中文字符后，按空格分割计算英文单词
    text_without_chinese = re.sub(r"[\u4e00-\u9fff]", " ", text)
    english_words = [w for w in text_without_chinese.split() if w.strip()]
    english_count = len(english_words)

    return chinese_count + english_count


def _display_volume_title(volume: Volume) -> str:
    title = volume.title.strip()
    return title or "未命名卷"


def _display_chapter_title(chapter: Chapter) -> str:
    title = chapter.title.strip()
    return title or "未命名章节"


def _match_rank(text: str, normalized_query: str) -> int:
    normalized_text = text.strip().lower()
    if not normalized_text:
        return 99
    if normalized_text == normalized_query:
        return 0
    if normalized_text.startswith(normalized_query):
        return 1
    if normalized_query in normalized_text:
        return 2
    return 99


async def _update_project_stats(session: AsyncSession, project_id: str) -> None:
    """
    更新项目的统计信息（字数和章节数）。

    Args:
        session: 数据库 session。
        project_id: 项目 ID。
    """
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        return

    # 更新章节数
    chapter_count = await chapter_repo.count_by_project(session, project_id)
    project.chapter_count = chapter_count

    # 更新总字数
    total_word_count = await chapter_repo.get_total_word_count(session, project_id)
    project.word_count = total_word_count

    project.updated_at = datetime.now(UTC)
    await project_repo.update(session, project)


async def _update_volume_stats(session: AsyncSession, volume_id: str) -> None:
    """更新卷的章节数缓存。"""
    volume = await volume_repo.get_by_id(session, volume_id)
    if volume is None:
        return
    volume.chapter_count = await chapter_repo.count_by_volume(session, volume_id)
    volume.updated_at = datetime.now(UTC)
    await volume_repo.update_volume(session, volume)


async def create_chapter(
    session: AsyncSession,
    project_id: str,
    volume_id: str,
    title: str,
    content: str = "",
    word_count: int | None = None,
) -> Chapter:
    """
    创建章节。

    Args:
        session: 数据库 session。
        project_id: 项目 ID。
        volume_id: 卷 ID。
        title: 章节标题。
        content: 章节内容，默认为空。
        word_count: 字数（前端计算），如果为 None 则后端计算。

    Returns:
        创建的章节实例。

    Raises:
        NotFoundError: 项目不存在。
    """
    # 检查项目是否存在
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"项目不存在: {project_id}")
    volume = await volume_repo.get_by_id(session, volume_id)
    if volume is None or volume.project_id != project_id:
        raise NotFoundError(f"卷不存在: {volume_id}")

    # 获取最大排序序号
    max_order = await chapter_repo.get_max_order(session, volume_id)

    # 使用前端传递的字数，或后端计算
    final_word_count = word_count if word_count is not None else _count_words(content)

    # 创建章节
    chapter = Chapter(
        project_id=project_id,
        volume_id=volume_id,
        title=title,
        content=content,
        word_count=final_word_count,
        order=max_order + 1,
    )
    chapter = await chapter_repo.create(session, chapter)

    await writing_activity_service.record_activity(
        session,
        project_id=project_id,
        chapter_id=chapter.id,
        chapter_title=chapter.title,
        source="user",
        operation="create",
        old_word_count=0,
        new_word_count=chapter.word_count,
    )

    # 更新项目统计
    await _update_volume_stats(session, volume_id)
    await _update_project_stats(session, project_id)

    from app.memory.chapter.summary_service import (
        maybe_enqueue_chapter_summary_for_new_chapter,
    )

    await maybe_enqueue_chapter_summary_for_new_chapter(session, chapter)

    from app.retrieval.chapter_index import safe_maybe_enqueue_auto_index
    from app.retrieval.index_status import schedule_emit_index_status

    await safe_maybe_enqueue_auto_index(session, project_id=project_id)
    schedule_emit_index_status(session, project_id)

    return chapter


async def get_chapter(session: AsyncSession, chapter_id: str) -> Chapter:
    """
    获取章节。

    Args:
        session: 数据库 session。
        chapter_id: 章节 ID。

    Returns:
        章节实例。

    Raises:
        NotFoundError: 章节不存在。
    """
    chapter = await chapter_repo.get_by_id(session, chapter_id)
    if chapter is None:
        raise NotFoundError(f"章节不存在: {chapter_id}")
    return chapter


async def list_chapters(
    session: AsyncSession,
    project_id: str,
) -> VolumeTreeResult:
    """
    获取项目卷-章树（章节不含正文内容）。

    Args:
        session: 数据库 session。
        project_id: 项目 ID。

    Returns:
        章节列表结果。

    Raises:
        NotFoundError: 项目不存在。
    """
    # 检查项目是否存在
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"项目不存在: {project_id}")

    volumes = await volume_repo.list_by_project(session, project_id)
    chapters = await chapter_repo.list_by_project(session, project_id)
    chapters_by_volume: dict[str, list[Chapter]] = {volume.id: [] for volume in volumes}
    for chapter in chapters:
        chapters_by_volume.setdefault(chapter.volume_id, []).append(chapter)
    groups = [
        VolumeChapterGroup(
            volume=volume,
            chapters=chapters_by_volume.get(volume.id, []),
        )
        for volume in volumes
    ]
    return VolumeTreeResult(volumes=groups, total_chapters=len(chapters))


async def search_mention_candidates(
    session: AsyncSession,
    project_id: str,
    query: str,
    *,
    limit: int = 20,
) -> list[MentionCandidate]:
    """搜索可插入对话的卷/章节 mention 候选项。"""
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"项目不存在: {project_id}")

    normalized_query = query.strip().lower()
    if not normalized_query:
        return []

    clamped_limit = max(1, min(limit, 50))
    matched_volumes = await volume_repo.search_by_project(
        session,
        project_id,
        normalized_query,
        limit=clamped_limit,
    )
    matched_chapters = await chapter_repo.search_with_volume_by_project(
        session,
        project_id,
        normalized_query,
        limit=clamped_limit,
    )

    scored_candidates: list[tuple[int, int, MentionCandidate]] = []

    for index, volume in enumerate(matched_volumes):
        title = _display_volume_title(volume)
        scored_candidates.append(
            (
                _match_rank(title, normalized_query),
                index,
                MentionCandidate(
                    kind="volume",
                    id=volume.id,
                    title=title,
                    label=title,
                ),
            )
        )

    base_index = len(scored_candidates)
    for offset, (chapter, volume) in enumerate(matched_chapters):
        chapter_title = _display_chapter_title(chapter)
        volume_title = _display_volume_title(volume)
        chapter_rank = _match_rank(chapter_title, normalized_query)
        volume_rank = _match_rank(volume_title, normalized_query)
        scored_candidates.append(
            (
                min(chapter_rank, volume_rank + 3),
                base_index + offset,
                MentionCandidate(
                    kind="chapter",
                    id=chapter.id,
                    title=chapter_title,
                    label=chapter_title,
                    description=volume_title,
                ),
            )
        )

    scored_candidates.sort(
        key=lambda item: (
            item[0],
            0 if item[2].kind == "volume" else 1,
            item[1],
        )
    )
    return [candidate for _, _, candidate in scored_candidates[:clamped_limit]]


@dataclass
class ChapterSearchMatch:
    """章节内容搜索匹配行。"""

    line_number: int
    line_text: str


@dataclass
class ChapterSearchResult:
    """章节内容搜索结果。"""

    chapter_id: str
    chapter_title: str
    volume_title: str
    matches: list[ChapterSearchMatch]


@dataclass
class ChapterSearchResponse:
    """章节内容搜索响应。"""

    results: list[ChapterSearchResult]
    total_chapters: int
    total_matches: int


async def search_chapters(
    session: AsyncSession,
    project_id: str,
    query: str,
) -> ChapterSearchResponse:
    """按内容搜索章节。"""
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"项目不存在: {project_id}")

    if not query.strip():
        return ChapterSearchResponse(results=[], total_chapters=0, total_matches=0)

    entries = await chapter_repo.search_by_content(session, project_id, query)

    results: list[ChapterSearchResult] = []
    total_matches = 0
    lower_query = query.lower()

    for chapter, volume in entries:
        lines = chapter.content.split("\n")
        matches: list[ChapterSearchMatch] = []
        for line_number, line in enumerate(lines, start=1):
            if lower_query in line.lower():
                matches.append(
                    ChapterSearchMatch(
                        line_number=line_number,
                        line_text=line,
                    )
                )

        if matches:
            results.append(
                ChapterSearchResult(
                    chapter_id=chapter.id,
                    chapter_title=_display_chapter_title(chapter),
                    volume_title=_display_volume_title(volume),
                    matches=matches,
                )
            )
            total_matches += len(matches)

    return ChapterSearchResponse(
        results=results,
        total_chapters=len(results),
        total_matches=total_matches,
    )


async def update_chapter(
    session: AsyncSession,
    chapter_id: str,
    title: str | None = None,
    content: str | None = None,
    word_count: int | None = None,
) -> Chapter:
    """
    更新章节。

    Args:
        session: 数据库 session。
        chapter_id: 章节 ID。
        title: 新标题，可选。
        content: 新内容，可选。
        word_count: 字数（前端计算），如果为 None 则后端计算。

    Returns:
        更新后的章节实例。

    Raises:
        NotFoundError: 章节不存在。
    """
    chapter = await get_chapter(session, chapter_id)
    old_word_count = chapter.word_count
    old_content = chapter.content

    title_changed = False
    if title is not None and title != chapter.title:
        chapter.title = title
        title_changed = True

    content_changed = False
    if content is not None and content != chapter.content:
        chapter.content = content
        # 优先使用前端传递的字数，否则后端计算
        chapter.word_count = (
            word_count if word_count is not None else _count_words(content)
        )
        content_changed = True
    elif word_count is not None and word_count != chapter.word_count:
        # 如果只传了 word_count 没传 content，也只在字数实际变化时更新
        chapter.word_count = word_count
        content_changed = True

    if title_changed or content_changed:
        chapter.updated_at = datetime.now(UTC)
    chapter = await chapter_repo.update_chapter(session, chapter)

    # 如果有任何变化，更新项目统计（包括 updated_at）
    if title_changed or content_changed:
        if content_changed:
            await writing_activity_service.record_activity(
                session,
                project_id=chapter.project_id,
                chapter_id=chapter.id,
                chapter_title=chapter.title,
                source="user",
                operation="update",
                old_word_count=old_word_count,
                new_word_count=chapter.word_count,
            )
        await _update_project_stats(session, chapter.project_id)
    if content is not None and content != old_content:
        from app.retrieval.chapter_index import (
            ChapterIndexIntegrationService,
            safe_maybe_enqueue_auto_index,
        )
        from app.retrieval.index_status import schedule_emit_index_status

        await ChapterIndexIntegrationService().mark_chapter_stale_if_changed(
            session,
            chapter,
        )
        await safe_maybe_enqueue_auto_index(session, project_id=chapter.project_id)
        schedule_emit_index_status(session, chapter.project_id)
    return chapter


async def delete_chapter(
    session: AsyncSession,
    chapter_id: str,
    *,
    record_activity: bool = True,
    activity_source: writing_activity_service.WritingActivitySource = "user",
    revision_id: str | None = None,
    task_id: str | None = None,
    agent_session_id: str | None = None,
) -> None:
    """
    删除章节。

    Args:
        session: 数据库 session。
        chapter_id: 章节 ID。

    Raises:
        NotFoundError: 章节不存在。
    """
    chapter = await get_chapter(session, chapter_id)
    project_id = chapter.project_id
    volume_id = chapter.volume_id
    deleted_order = chapter.order
    old_title = chapter.title
    old_word_count = chapter.word_count

    from app.retrieval.chapter_index import ChapterIndexIntegrationService

    await ChapterIndexIntegrationService().delete_chapter_index(session, chapter)

    from app.retrieval.index_status import schedule_emit_index_status

    schedule_emit_index_status(session, project_id)

    await chapter_summary_repo.delete_by_chapter_id(session, chapter_id)
    long_term_summaries = (
        await chapter_summary_repo.list_long_term_summaries_by_project(
            session, project_id
        )
    )
    affected_ranges = list(
        {
            (summary.start_order, summary.end_order)
            for summary in long_term_summaries
            if summary.start_order is not None
            and summary.end_order is not None
            and summary.end_order >= deleted_order
        }
    )
    if affected_ranges:
        await chapter_summary_repo.delete_long_term_summaries_by_ranges(
            session, project_id, affected_ranges
        )

    # 删除章节
    await chapter_repo.delete(session, chapter)

    if record_activity:
        await writing_activity_service.record_activity(
            session,
            project_id=project_id,
            chapter_id=chapter_id,
            chapter_title=old_title,
            source=activity_source,
            operation="delete",
            old_word_count=old_word_count,
            new_word_count=0,
            revision_id=revision_id,
            task_id=task_id,
            agent_session_id=agent_session_id,
        )

    # 调整后续章节的顺序
    max_order = await chapter_repo.get_max_order(session, volume_id)
    if deleted_order <= max_order:
        # 将所有 order > deleted_order 的章节 order 减 1
        await chapter_repo.shift_orders(
            session, volume_id, deleted_order + 1, max_order, -1
        )

    # 更新项目统计
    await _update_volume_stats(session, volume_id)
    await _update_project_stats(session, project_id)


async def reorder_chapters(
    session: AsyncSession,
    volume_id: str,
    chapter_ids: list[str],
) -> list[Chapter]:
    """
    批量重排章节顺序。

    Args:
        session: 数据库 session。
        volume_id: 卷 ID。
        chapter_ids: 按新顺序排列的章节 ID 列表。

    Returns:
        更新后的章节列表。

    Raises:
        NotFoundError: 章节不存在或不属于指定卷。
        ValueError: 章节数量不匹配。
    """
    chapters = await chapter_repo.get_by_ids(session, chapter_ids)
    chapter_map = {c.id: c for c in chapters}

    if len(chapters) != len(chapter_ids):
        missing = [cid for cid in chapter_ids if cid not in chapter_map]
        raise NotFoundError(f"章节不存在: {missing}")

    for chapter in chapters:
        if chapter.volume_id != volume_id:
            raise ValueError(f"章节 {chapter.id} 不属于卷 {volume_id}")

    orders: dict[str, int] = {}
    for idx, cid in enumerate(chapter_ids, start=1):
        orders[cid] = idx

    await chapter_repo.update_orders(session, orders)

    updated_chapters = await chapter_repo.get_by_ids(session, chapter_ids)
    order_lookup = {cid: idx for idx, cid in enumerate(chapter_ids)}
    updated_chapters.sort(key=lambda c: order_lookup.get(c.id, 0))
    return updated_chapters


async def move_chapter_to_volume(
    session: AsyncSession,
    chapter_id: str,
    volume_id: str,
    *,
    record_activity: bool = True,
    activity_source: writing_activity_service.WritingActivitySource = "user",
    revision_id: str | None = None,
    task_id: str | None = None,
    agent_session_id: str | None = None,
) -> Chapter:
    """跨卷移动章节，追加到目标卷末尾。"""
    chapter = await get_chapter(session, chapter_id)
    source_volume_id = chapter.volume_id
    if source_volume_id == volume_id:
        return chapter

    target_volume = await volume_repo.get_by_id(session, volume_id)
    if target_volume is None or target_volume.project_id != chapter.project_id:
        raise NotFoundError(f"卷不存在: {volume_id}")

    old_order = chapter.order
    chapter.order = 0
    await chapter_repo.update_chapter(session, chapter)

    source_max_order = await chapter_repo.get_max_order(session, source_volume_id)
    if old_order <= source_max_order:
        await chapter_repo.shift_orders(
            session, source_volume_id, old_order + 1, source_max_order, -1
        )

    target_max_order = await chapter_repo.get_max_order(session, volume_id)
    chapter.volume_id = volume_id
    chapter.order = target_max_order + 1
    chapter.updated_at = datetime.now(UTC)
    chapter = await chapter_repo.update_chapter(session, chapter)

    await _update_volume_stats(session, source_volume_id)
    await _update_volume_stats(session, volume_id)
    await _update_project_stats(session, chapter.project_id)
    from app.retrieval.chapter_index import (
        ChapterIndexIntegrationService,
        safe_maybe_enqueue_auto_index,
    )
    from app.retrieval.index_status import schedule_emit_index_status

    await ChapterIndexIntegrationService().mark_chapter_stale_if_indexed(
        session,
        chapter,
    )
    await safe_maybe_enqueue_auto_index(session, project_id=chapter.project_id)
    schedule_emit_index_status(session, chapter.project_id)
    if record_activity:
        await writing_activity_service.record_activity(
            session,
            project_id=chapter.project_id,
            chapter_id=chapter.id,
            chapter_title=chapter.title,
            source=activity_source,
            operation="move_to_volume",
            old_word_count=chapter.word_count,
            new_word_count=chapter.word_count,
            revision_id=revision_id,
            task_id=task_id,
            agent_session_id=agent_session_id,
        )
    return chapter
