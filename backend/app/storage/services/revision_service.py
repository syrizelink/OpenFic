# -*- coding: utf-8 -*-
"""Revision/commit/snapshot deletion helpers and orphan cleanup.

These functions centralize the cascade rules for revision history:

- Deleting a project/task also deletes its revisions, commits, and snapshots.
- Deleting commit/snapshot rows garbage-collects content blobs that are no
  longer referenced by any surviving revision child row.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import Select, and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.commit import Commit
from app.storage.models.project import Project
from app.storage.models.revision import Revision
from app.storage.models.revision_chapter_snapshot import RevisionChapterSnapshot
from app.storage.models.revision_character_snapshot import RevisionCharacterSnapshot
from app.storage.models.revision_content_blob import RevisionContentBlob
from app.storage.models.revision_note_snapshot import (
    RevisionNoteCategorySnapshot,
    RevisionNoteSnapshot,
)
from app.storage.models.revision_world_entry_snapshot import RevisionWorldEntrySnapshot
from app.storage.models.task import Task

# Tables whose rows point at a revision.
_REVISION_CHILD_MODELS = (
    Commit,
    RevisionChapterSnapshot,
    RevisionNoteSnapshot,
    RevisionNoteCategorySnapshot,
    RevisionCharacterSnapshot,
    RevisionWorldEntrySnapshot,
)

# Every column that references a RevisionContentBlob id.
_BLOB_REFERENCE_COLUMNS = (
    (Commit, col(Commit.snapshot_content_blob_id)),
    (Commit, col(Commit.new_content_blob_id)),
    (RevisionChapterSnapshot, col(RevisionChapterSnapshot.content_blob_id)),
    (RevisionNoteSnapshot, col(RevisionNoteSnapshot.content_blob_id)),
    (RevisionCharacterSnapshot, col(RevisionCharacterSnapshot.description_blob_id)),
    (RevisionWorldEntrySnapshot, col(RevisionWorldEntrySnapshot.content_blob_id)),
)

_BLOB_GC_BATCH = 500


async def _gc_revision_blobs(session: AsyncSession, blob_ids: set[str]) -> int:
    """Delete content blobs that are no longer referenced by any child row."""
    blob_ids = {blob_id for blob_id in blob_ids if blob_id}
    if not blob_ids:
        return 0

    deleted = 0
    ordered = list(blob_ids)
    for start in range(0, len(ordered), _BLOB_GC_BATCH):
        chunk = ordered[start : start + _BLOB_GC_BATCH]
        stmt = delete(RevisionContentBlob).where(col(RevisionContentBlob.id).in_(chunk))
        for _model, blob_col in _BLOB_REFERENCE_COLUMNS:
            referenced = select(blob_col).where(blob_col.is_not(None))
            stmt = stmt.where(~col(RevisionContentBlob.id).in_(referenced))
        result = await session.execute(stmt)
        deleted += int(getattr(result, "rowcount", 0) or 0)
    return deleted


async def _delete_children_and_collect_blobs(
    session: AsyncSession,
    revision_condition: Callable[[Any], Any],
) -> tuple[int, set[str]]:
    """Delete child rows matching ``revision_condition`` and collect blob ids.

    ``revision_condition(model)`` returns the SQL predicate on ``model.revision_id``.
    """
    deleted_rows = 0
    blob_ids: set[str] = set()

    for model in _REVISION_CHILD_MODELS:
        condition = revision_condition(model)

        for ref_model, blob_col in _BLOB_REFERENCE_COLUMNS:
            if ref_model is not model:
                continue
            result = await session.execute(
                select(blob_col).where(condition, blob_col.is_not(None))
            )
            blob_ids.update(blob_id for blob_id in result.scalars().all() if blob_id is not None)

        result = await session.execute(delete(model).where(condition))
        deleted_rows += int(getattr(result, "rowcount", 0) or 0)

    return deleted_rows, blob_ids


async def _delete_revision_data(
    session: AsyncSession,
    revision_ids_subquery: Select[Any],
) -> int:
    """Delete child rows, revisions, and now-unreferenced blobs for revisions
    selected by ``revision_ids_subquery``."""
    deleted_rows, blob_ids = await _delete_children_and_collect_blobs(
        session,
        lambda model: model.revision_id.in_(revision_ids_subquery),
    )

    result = await session.execute(
        delete(Revision).where(col(Revision.id).in_(revision_ids_subquery))
    )
    deleted_rows += int(getattr(result, "rowcount", 0) or 0)

    deleted_rows += await _gc_revision_blobs(session, blob_ids)
    await session.flush()
    return deleted_rows


async def delete_revision_data_by_project(
    session: AsyncSession,
    project_id: str,
) -> int:
    """Cascade-delete all revision history owned by a project."""
    revision_ids = select(col(Revision.id)).where(col(Revision.project_id) == project_id)
    return await _delete_revision_data(session, revision_ids)


async def delete_revision_data_by_tasks(
    session: AsyncSession,
    task_ids: list[str],
) -> int:
    """Cascade-delete revision history owned by one or more tasks."""
    if not task_ids:
        return 0
    revision_ids = select(col(Revision.id)).where(col(Revision.task_id).in_(task_ids))
    return await _delete_revision_data(session, revision_ids)


async def cleanup_orphaned_revision_data(session: AsyncSession) -> int:
    """Delete revision history left behind by deleted projects/tasks.

    Safe to run on every startup. Returns the number of deleted rows (including
    garbage-collected blobs).
    """
    existing_project_ids = select(col(Project.id))
    existing_task_ids = select(col(Task.id))
    existing_revision_ids = select(col(Revision.id))

    orphan_revision_ids = select(col(Revision.id)).where(
        or_(
            col(Revision.project_id).not_in(existing_project_ids),
            and_(
                col(Revision.task_id).is_not(None),
                col(Revision.task_id).not_in(existing_task_ids),
            ),
        )
    )

    deleted_rows, blob_ids = await _delete_children_and_collect_blobs(
        session,
        lambda model: or_(
            model.revision_id.not_in(existing_revision_ids),
            model.revision_id.in_(orphan_revision_ids),
        ),
    )

    result = await session.execute(
        delete(Revision).where(col(Revision.id).in_(orphan_revision_ids))
    )
    deleted_rows += int(getattr(result, "rowcount", 0) or 0)

    deleted_rows += await _gc_revision_blobs(session, blob_ids)
    await session.flush()
    return deleted_rows
