# -*- coding: utf-8 -*-
"""Repository for chapter retrieval index states."""

from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.retrieval_chapter_index_state import RetrievalChapterIndexState


async def get_by_project_and_chapter(
    session: AsyncSession,
    *,
    project_id: str,
    chapter_id: str,
    index_key: str,
) -> RetrievalChapterIndexState | None:
    result = await session.execute(
        select(RetrievalChapterIndexState).where(
            col(RetrievalChapterIndexState.project_id) == project_id,
            col(RetrievalChapterIndexState.chapter_id) == chapter_id,
            col(RetrievalChapterIndexState.index_key) == index_key,
        )
    )
    return result.scalar_one_or_none()


async def list_by_project(
    session: AsyncSession,
    *,
    project_id: str,
    index_key: str,
) -> list[RetrievalChapterIndexState]:
    result = await session.execute(
        select(RetrievalChapterIndexState).where(
            col(RetrievalChapterIndexState.project_id) == project_id,
            col(RetrievalChapterIndexState.index_key) == index_key,
        )
    )
    return list(result.scalars().all())


async def save(
    session: AsyncSession,
    row: RetrievalChapterIndexState,
) -> RetrievalChapterIndexState:
    row.updated_at = datetime.now(UTC)
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def delete_by_chapter_id(session: AsyncSession, chapter_id: str) -> None:
    await session.execute(
        delete(RetrievalChapterIndexState).where(
            col(RetrievalChapterIndexState.chapter_id) == chapter_id
        )
    )
    await session.flush()


async def mark_all_needs_rebuild(session: AsyncSession) -> None:
    await session.execute(
        update(RetrievalChapterIndexState).values(
            status="needs_rebuild",
            job_id=None,
            item_id=None,
            error_message=None,
            updated_at=datetime.now(UTC),
        )
    )
    await session.flush()


async def mark_project_needs_rebuild(
    session: AsyncSession,
    *,
    project_id: str,
    index_key: str,
) -> None:
    """将单个项目下全部章节索引状态标记为 needs_rebuild（用于 schema 升级等场景）。"""
    await session.execute(
        update(RetrievalChapterIndexState)
        .where(
            col(RetrievalChapterIndexState.project_id) == project_id,
            col(RetrievalChapterIndexState.index_key) == index_key,
        )
        .values(
            status="needs_rebuild",
            job_id=None,
            item_id=None,
            error_message=None,
            updated_at=datetime.now(UTC),
        )
    )
    await session.flush()
