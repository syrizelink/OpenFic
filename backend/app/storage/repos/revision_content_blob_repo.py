# -*- coding: utf-8 -*-
"""Content-addressed blob repository for revision/commit large text payloads."""

from __future__ import annotations

import hashlib
import zlib

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import set_committed_value
from sqlmodel import col

from app.storage.models.revision_content_blob import RevisionContentBlob

# Text shorter than this stays inline in the owning row to avoid blob-table
# churn and compression overhead for tiny strings.
INLINE_THRESHOLD = 512

_COMPRESS_LEVEL = 6


def blob_id_for_text(text: str) -> str:
    """Return the content address (sha256 hex) for raw UTF-8 ``text``."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compress_text(text: str) -> bytes:
    return zlib.compress(text.encode("utf-8"), level=_COMPRESS_LEVEL)


def decompress_text(data: bytes) -> str:
    return zlib.decompress(data).decode("utf-8")


async def put(session: AsyncSession, text: str | None) -> str | None:
    """Store ``text`` as a deduplicated blob and return its id.

    Returns ``None`` when the value should stay inline: ``None``, empty, or
    shorter than ``INLINE_THRESHOLD``.
    """
    if not text or len(text) < INLINE_THRESHOLD:
        return None
    blob_id = blob_id_for_text(text)
    raw = text.encode("utf-8")
    statement = (
        sqlite_insert(RevisionContentBlob)
        .values(
            id=blob_id,
            data=zlib.compress(raw, level=_COMPRESS_LEVEL),
            raw_size=len(raw),
        )
        .on_conflict_do_nothing(index_elements=[RevisionContentBlob.id])
    )
    await session.execute(statement)
    return blob_id


async def get(session: AsyncSession, blob_id: str | None) -> str | None:
    """Fetch and decompress a single blob, or ``None`` if absent/not referenced."""
    if not blob_id:
        return None
    blob = await session.get(RevisionContentBlob, blob_id)
    if blob is None:
        return None
    return decompress_text(blob.data)


async def get_many(session: AsyncSession, blob_ids: set[str]) -> dict[str, str]:
    """Fetch and decompress multiple blobs keyed by blob id."""
    if not blob_ids:
        return {}
    result = await session.execute(
        select(RevisionContentBlob).where(col(RevisionContentBlob.id).in_(blob_ids))
    )
    return {
        blob.id: decompress_text(blob.data)
        for blob in result.scalars().all()
    }


async def hydrate_content(
    session: AsyncSession,
    rows,
    *,
    blob_id_attr: str,
    content_attr: str,
) -> None:
    """Batch-populate ``content_attr`` on each row from its ``blob_id_attr``.

    Rows without a blob reference keep their inline value untouched. Values are
    written as committed (not dirty) so later flushes never write blob content
    back into the inline column.
    """
    blob_ids = {
        getattr(row, blob_id_attr)
        for row in rows
        if getattr(row, blob_id_attr, None)
    }
    if not blob_ids:
        return
    contents = await get_many(session, blob_ids)
    for row in rows:
        blob_id = getattr(row, blob_id_attr, None)
        if blob_id:
            set_committed_value(row, content_attr, contents.get(blob_id))

