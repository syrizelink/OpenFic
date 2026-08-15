# -*- coding: utf-8 -*-
"""Revision world-entry snapshot repositories."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.revision_world_entry_snapshot import RevisionWorldEntrySnapshot
from app.storage.repos import revision_content_blob_repo


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
    snapshots = list(result.scalars().all())
    await revision_content_blob_repo.hydrate_content(
        session,
        snapshots,
        blob_id_attr="content_blob_id",
        content_attr="content",
    )
    return snapshots
