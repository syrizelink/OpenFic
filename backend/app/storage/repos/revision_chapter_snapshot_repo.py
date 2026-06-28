# -*- coding: utf-8 -*-
"""Revision chapter snapshot repository."""

from sqlalchemy import delete as sql_delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.revision_chapter_snapshot import RevisionChapterSnapshot


async def create(
    session: AsyncSession,
    snapshot: RevisionChapterSnapshot,
) -> RevisionChapterSnapshot:
    session.add(snapshot)
    await session.flush()
    await session.refresh(snapshot)
    return snapshot


async def replace_for_revision(
    session: AsyncSession,
    revision_id: str,
    snapshots: list[RevisionChapterSnapshot],
) -> list[RevisionChapterSnapshot]:
    await session.execute(
        sql_delete(RevisionChapterSnapshot).where(
            col(RevisionChapterSnapshot.revision_id) == revision_id
        )
    )
    if snapshots:
        session.add_all(snapshots)
    await session.flush()
    for snapshot in snapshots:
        await session.refresh(snapshot)
    return snapshots


async def list_by_revision(
    session: AsyncSession,
    revision_id: str,
) -> list[RevisionChapterSnapshot]:
    result = await session.execute(
        select(RevisionChapterSnapshot)
        .where(col(RevisionChapterSnapshot.revision_id) == revision_id)
        .order_by(col(RevisionChapterSnapshot.chapter_order).asc())
    )
    return list(result.scalars().all())
