# -*- coding: utf-8 -*-
"""Revision character snapshot repositories."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.revision_character_snapshot import RevisionCharacterSnapshot
from app.storage.repos import revision_content_blob_repo


async def create(
    session: AsyncSession,
    snapshot: RevisionCharacterSnapshot,
) -> RevisionCharacterSnapshot:
    session.add(snapshot)
    await session.flush()
    await session.refresh(snapshot)
    return snapshot


async def list_by_revision(
    session: AsyncSession,
    revision_id: str,
) -> list[RevisionCharacterSnapshot]:
    result = await session.execute(
        select(RevisionCharacterSnapshot)
        .where(col(RevisionCharacterSnapshot.revision_id) == revision_id)
        .order_by(col(RevisionCharacterSnapshot.created_at).asc())
    )
    snapshots = list(result.scalars().all())
    await revision_content_blob_repo.hydrate_content(
        session,
        snapshots,
        blob_id_attr="description_blob_id",
        content_attr="description",
    )
    return snapshots
