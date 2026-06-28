# -*- coding: utf-8 -*-
"""
Mention Service - 统一的 mention 候选搜索逻辑。
"""

from dataclasses import dataclass
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.storage.repos import (
    chapter_repo,
    note_category_repo,
    note_repo,
    project_repo,
    volume_repo,
)


@dataclass(frozen=True)
class MentionCandidate:
    kind: Literal["volume", "chapter", "note", "note_category"]
    id: str
    title: str
    label: str
    description: str | None = None


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


def _display_title(title: str) -> str:
    return title.strip() or "未命名"


async def search_all_mention_candidates(
    session: AsyncSession,
    project_id: str,
    query: str,
    *,
    limit: int = 20,
    kind: Literal["volume", "chapter", "note", "note_category"] | None = None,
) -> list[MentionCandidate]:
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"项目不存在: {project_id}")

    normalized_query = query.strip().lower()
    if not normalized_query:
        return []

    clamped_limit = max(1, min(limit, 50))
    scored_candidates: list[tuple[int, int, MentionCandidate]] = []

    if kind is None or kind == "volume":
        matched_volumes = await volume_repo.search_by_project(
            session, project_id, normalized_query, limit=clamped_limit
        )
        for index, volume in enumerate(matched_volumes):
            title = _display_title(volume.title)
            scored_candidates.append(
                (
                    _match_rank(title, normalized_query),
                    index,
                    MentionCandidate(
                        kind="volume", id=volume.id, title=title, label=title
                    ),
                )
            )

    if kind is None or kind == "chapter":
        matched_chapters = await chapter_repo.search_with_volume_by_project(
            session, project_id, normalized_query, limit=clamped_limit
        )
        base_index = len(scored_candidates)
        for offset, (chapter, volume) in enumerate(matched_chapters):
            chapter_title = _display_title(chapter.title)
            volume_title = _display_title(volume.title)
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

    if kind is None or kind == "note":
        matched_notes = await note_repo.search_mention_candidates(
            session,
            project_id,
            normalized_query,
            limit=clamped_limit,
            include_hidden=False,
        )
        base_index = len(scored_candidates)
        for offset, note in enumerate(matched_notes):
            note_title = _display_title(note.title)
            scored_candidates.append(
                (
                    _match_rank(note_title, normalized_query),
                    base_index + offset,
                    MentionCandidate(
                        kind="note",
                        id=note.id,
                        title=note_title,
                        label=note_title,
                    ),
                )
            )

    if kind is None or kind == "note_category":
        matched_categories = await note_category_repo.search_mention_candidates(
            session,
            project_id,
            normalized_query,
            limit=clamped_limit,
        )
        base_index = len(scored_candidates)
        for offset, category in enumerate(matched_categories):
            category_title = _display_title(category.title)
            scored_candidates.append(
                (
                    _match_rank(category_title, normalized_query),
                    base_index + offset,
                    MentionCandidate(
                        kind="note_category",
                        id=category.id,
                        title=category_title,
                        label=category_title,
                    ),
                )
            )

    scored_candidates.sort(
        key=lambda item: (
            item[0],
            {"volume": 0, "chapter": 1, "note": 2, "note_category": 3}.get(
                item[2].kind, 4
            ),
            item[1],
        )
    )
    return [candidate for _, _, candidate in scored_candidates[:clamped_limit]]
