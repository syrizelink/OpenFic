# -*- coding: utf-8 -*-
"""Revision note and note-category snapshot repositories."""

from sqlalchemy import delete as sql_delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.revision_note_snapshot import (
    RevisionNoteCategorySnapshot,
    RevisionNoteSnapshot,
)


async def create(
    session: AsyncSession,
    snapshot: RevisionNoteSnapshot,
) -> RevisionNoteSnapshot:
    session.add(snapshot)
    await session.flush()
    await session.refresh(snapshot)
    return snapshot


async def replace_for_revision(
    session: AsyncSession,
    revision_id: str,
    snapshots: list[RevisionNoteSnapshot],
) -> list[RevisionNoteSnapshot]:
    await session.execute(
        sql_delete(RevisionNoteSnapshot).where(
            col(RevisionNoteSnapshot.revision_id) == revision_id
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
) -> list[RevisionNoteSnapshot]:
    result = await session.execute(
        select(RevisionNoteSnapshot)
        .where(col(RevisionNoteSnapshot.revision_id) == revision_id)
        .order_by(col(RevisionNoteSnapshot.title).asc())
    )
    return list(result.scalars().all())


async def create_category_snapshot(
    session: AsyncSession,
    snapshot: RevisionNoteCategorySnapshot,
) -> RevisionNoteCategorySnapshot:
    session.add(snapshot)
    await session.flush()
    await session.refresh(snapshot)
    return snapshot


async def list_category_snapshots_by_revision(
    session: AsyncSession,
    revision_id: str,
) -> list[RevisionNoteCategorySnapshot]:
    result = await session.execute(
        select(RevisionNoteCategorySnapshot)
        .where(col(RevisionNoteCategorySnapshot.revision_id) == revision_id)
        .order_by(col(RevisionNoteCategorySnapshot.title).asc())
    )
    return list(result.scalars().all())
