# -*- coding: utf-8 -*-
"""Repository for chapter retrieval index states."""

from datetime import UTC, datetime

from sqlalchemy import case, delete, select, update
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


async def queue_chapters_for_job(
    session: AsyncSession,
    *,
    project_id: str,
    index_key: str,
    chapter_ids: list[str],
    embedding_model_ref_id: str,
    job_id: str,
    item_ids_by_chapter_id: dict[str, str],
) -> None:
    if not chapter_ids:
        return
    result = await session.execute(
        select(RetrievalChapterIndexState)
        .where(col(RetrievalChapterIndexState.project_id) == project_id)
        .where(col(RetrievalChapterIndexState.index_key) == index_key)
        .where(col(RetrievalChapterIndexState.chapter_id).in_(chapter_ids))
    )
    states = list(result.scalars().all())
    states_by_chapter_id = {state.chapter_id: state for state in states}
    now = datetime.now(UTC)
    new_states = [
        RetrievalChapterIndexState(
            project_id=project_id,
            chapter_id=chapter_id,
            index_key=index_key,
            status="queued",
            embedding_model_ref_id=embedding_model_ref_id,
            job_id=job_id,
            item_id=item_ids_by_chapter_id[chapter_id],
        )
        for chapter_id in chapter_ids
        if chapter_id not in states_by_chapter_id
    ]
    if new_states:
        session.add_all(new_states)

    existing_chapter_ids = [
        chapter_id for chapter_id in chapter_ids if chapter_id in states_by_chapter_id
    ]
    if existing_chapter_ids:
        await session.execute(
            update(RetrievalChapterIndexState)
            .where(col(RetrievalChapterIndexState.project_id) == project_id)
            .where(col(RetrievalChapterIndexState.index_key) == index_key)
            .where(col(RetrievalChapterIndexState.chapter_id).in_(existing_chapter_ids))
            .values(
                status="queued",
                embedding_model_ref_id=embedding_model_ref_id,
                job_id=job_id,
                item_id=case(
                    item_ids_by_chapter_id,
                    value=col(RetrievalChapterIndexState.chapter_id),
                ),
                error_message=None,
                updated_at=now,
            )
        )
    await session.flush()


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


async def reset_active_states_for_job(session: AsyncSession, *, job_id: str) -> None:
    await session.execute(
        update(RetrievalChapterIndexState)
        .where(col(RetrievalChapterIndexState.job_id) == job_id)
        .where(col(RetrievalChapterIndexState.status).in_({"queued", "indexing"}))
        .values(
            status="needs_rebuild",
            job_id=None,
            item_id=None,
            error_message=None,
            updated_at=datetime.now(UTC),
        )
    )
    await session.flush()


async def fail_active_states_for_job(
    session: AsyncSession,
    *,
    job_id: str,
    error_message: str,
) -> None:
    await session.execute(
        update(RetrievalChapterIndexState)
        .where(col(RetrievalChapterIndexState.job_id) == job_id)
        .where(col(RetrievalChapterIndexState.status).in_({"queued", "indexing"}))
        .values(
            status="failed",
            error_message=error_message,
            updated_at=datetime.now(UTC),
        )
    )
    await session.flush()
