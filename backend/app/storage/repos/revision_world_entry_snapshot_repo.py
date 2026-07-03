# -*- coding: utf-8 -*-
"""Revision world-entry snapshot repositories."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.revision_world_entry_snapshot import RevisionWorldEntrySnapshot


async def create(
    session: AsyncSession,
    snapshot: RevisionWorldEntrySnapshot,
) -> RevisionWorldEntrySnapshot:
    session.add(snapshot)
    await session.flush()
    await session.refresh(snapshot)
    return snapshot


async def list_by_revision(
    session: AsyncSession,
    revision_id: str,
) -> list[RevisionWorldEntrySnapshot]:
    result = await session.execute(
        select(RevisionWorldEntrySnapshot)
        .where(col(RevisionWorldEntrySnapshot.revision_id) == revision_id)
        .order_by(col(RevisionWorldEntrySnapshot.entry_order).asc())
    )
    return list(result.scalars().all())
