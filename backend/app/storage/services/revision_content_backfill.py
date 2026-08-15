# -*- coding: utf-8 -*-
"""One-time backfill that rewrites inline revision/commit text into the
deduplicated, compressed content-blob table.

This is a data (DML) migration kept separate from the Alembic schema migration:
it can run on large existing databases with progress reporting and partial
commit, and it is idempotent via a marker row so it runs at most once.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models.commit import Commit
from app.storage.models.revision_character_snapshot import RevisionCharacterSnapshot
from app.storage.models.revision_chapter_snapshot import RevisionChapterSnapshot
from app.storage.models.revision_note_snapshot import RevisionNoteSnapshot
from app.storage.models.revision_world_entry_snapshot import RevisionWorldEntrySnapshot
from app.storage.repos import revision_content_blob_repo

_MARKER_TABLE = "openfic_maintenance_migrations"
_MARKER = "revision_content_blobs_backfill_v1"
_BATCH_SIZE = 500
_PROGRESS_STEP = 10  # emit progress at each 10% boundary

# (model, id column, content column, blob-id column)
_FIELD_SPECS: tuple[tuple[Any, Any, Any, Any], ...] = (
    (Commit, Commit.id, Commit.snapshot_content, Commit.snapshot_content_blob_id),
    (Commit, Commit.id, Commit.new_content, Commit.new_content_blob_id),
    (
        RevisionChapterSnapshot,
        RevisionChapterSnapshot.id,
        RevisionChapterSnapshot.content,
        RevisionChapterSnapshot.content_blob_id,
    ),
    (
        RevisionNoteSnapshot,
        RevisionNoteSnapshot.id,
        RevisionNoteSnapshot.content,
        RevisionNoteSnapshot.content_blob_id,
    ),
    (
        RevisionWorldEntrySnapshot,
        RevisionWorldEntrySnapshot.id,
        RevisionWorldEntrySnapshot.content,
        RevisionWorldEntrySnapshot.content_blob_id,
    ),
    (
        RevisionCharacterSnapshot,
        RevisionCharacterSnapshot.id,
        RevisionCharacterSnapshot.description,
        RevisionCharacterSnapshot.description_blob_id,
    ),
)

BackfillProgress = Callable[[str, float | None, int, int], None]


async def _ensure_marker_table(session: AsyncSession) -> None:
    await session.execute(
        text(
            f"CREATE TABLE IF NOT EXISTS {_MARKER_TABLE} ("
            "name TEXT PRIMARY KEY"
            ")"
        )
    )
    await session.commit()


async def _has_completed(session: AsyncSession) -> bool:
    row = (
        await session.execute(
            text(f"SELECT 1 FROM {_MARKER_TABLE} WHERE name = :name"),
            {"name": _MARKER},
        )
    ).first()
    return row is not None


async def _count_eligible(
    session: AsyncSession,
    model: Any,
    content_col: Any,
    blob_id_col: Any,
) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(model)
        .where(
            content_col.is_not(None),
            func.length(content_col) >= revision_content_blob_repo.INLINE_THRESHOLD,
            blob_id_col.is_(None),
        )
    )
    return int(result.scalar_one())


async def _backfill_field(
    session: AsyncSession,
    model: Any,
    id_col: Any,
    content_col: Any,
    blob_id_col: Any,
    processed: int,
    total: int,
    progress_callback: BackfillProgress | None,
) -> int:
    last_id: str | None = None
    next_emit = _PROGRESS_STEP / 100.0
    while True:
        stmt = (
            select(id_col, content_col)
            .where(
                content_col.is_not(None),
                func.length(content_col) >= revision_content_blob_repo.INLINE_THRESHOLD,
                blob_id_col.is_(None),
            )
            .order_by(id_col)
            .limit(_BATCH_SIZE)
        )
        if last_id is not None:
            stmt = stmt.where(id_col > last_id)
        rows = (await session.execute(stmt)).all()
        if not rows:
            break

        for row_id, content in rows:
            blob_id = await revision_content_blob_repo.put(session, content)
            await session.execute(
                update(model)
                .where(id_col == row_id)
                .values({content_col: None, blob_id_col: blob_id})
            )
        await session.commit()

        last_id = rows[-1][0]
        processed += len(rows)
        if progress_callback is not None and total > 0:
            fraction = processed / total
            while fraction >= next_emit and next_emit < 1.0:
                progress_callback("backfilling", next_emit, processed, total)
                next_emit += _PROGRESS_STEP / 100.0
    return processed


async def backfill_revision_content_blobs(
    session: AsyncSession,
    *,
    progress_callback: BackfillProgress | None = None,
) -> int:
    """Rewrite inline long text into deduplicated, compressed blobs.

    Returns the number of rows rewritten (0 when already completed or nothing
    eligible). Idempotent and resumable: partially migrated rows are skipped on
    the next run because their blob-id column is already set.
    """
    await _ensure_marker_table(session)
    if await _has_completed(session):
        if progress_callback is not None:
            progress_callback("backfilling", 1.0, 0, 0)
        return 0

    totals = [
        await _count_eligible(session, model, content_col, blob_id_col)
        for model, _, content_col, blob_id_col in _FIELD_SPECS
    ]
    total = sum(totals)
    if total == 0:
        await session.execute(
            text(f"INSERT INTO {_MARKER_TABLE} (name) VALUES (:name)"),
            {"name": _MARKER},
        )
        await session.commit()
        if progress_callback is not None:
            progress_callback("backfilling", 1.0, 0, 0)
        return 0

    if progress_callback is not None:
        progress_callback("backfilling", None, 0, total)

    processed = 0
    for model, id_col, content_col, blob_id_col in _FIELD_SPECS:
        processed = await _backfill_field(
            session,
            model,
            id_col,
            content_col,
            blob_id_col,
            processed,
            total,
            progress_callback,
        )

    await session.execute(
        text(f"INSERT INTO {_MARKER_TABLE} (name) VALUES (:name)"),
        {"name": _MARKER},
    )
    await session.commit()

    if progress_callback is not None:
        progress_callback("backfilling", 1.0, processed, total)
    return processed
