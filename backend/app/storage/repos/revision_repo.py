# -*- coding: utf-8 -*-
"""
Revision Repository - lapisan akses data versi.
"""

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.revision import Revision


async def create(session: AsyncSession, revision: Revision) -> Revision:
    """
    Membuat versi.

    Args:
        session: session basis data.
        revision: Instance versi.

    Returns:
        Instance versi setelah dibuat.
    """
    session.add(revision)
    await session.flush()
    await session.refresh(revision)
    return revision


async def get_by_id(session: AsyncSession, revision_id: str) -> Revision | None:
    """
    Mengambil versi berdasarkan ID.

    Args:
        session: session basis data.
        revision_id: ID versi.

    Returns:
        Instance versi, atau None bila tidak ada.
    """
    result = await session.execute(
        select(Revision).where(col(Revision.id) == revision_id)
    )
    return result.scalar_one_or_none()


async def list_by_project(
    session: AsyncSession,
    project_id: str,
    only_checkpoints: bool = False,
    offset: int = 0,
    limit: int = 50,
) -> list[Revision]:
    """
    Mengambil daftar versi sebuah proyek.

    Args:
        session: session basis data.
        project_id: ID proyek.
        only_checkpoints: Apakah hanya mengembalikan checkpoint.
        offset: Offset.
        limit: Jumlah per halaman.

    Returns:
        Daftar versi, urut waktu pembuatan menurun.
    """
    query = select(Revision).where(col(Revision.project_id) == project_id)

    if only_checkpoints:
        query = query.where(col(Revision.is_checkpoint))

    query = query.order_by(col(Revision.created_at).desc()).offset(offset).limit(limit)

    result = await session.execute(query)
    return list(result.scalars().all())


async def list_by_agent_session_from_seq(
    session: AsyncSession,
    agent_session_id: str,
    user_message_seq: int,
) -> list[Revision]:
    """List non-rollback agent revisions from a user message seq onward."""
    result = await session.execute(
        select(Revision)
        .where(col(Revision.agent_session_id) == agent_session_id)
        .where(col(Revision.revision_type) == "agent")
        .where(col(Revision.status) != "rolled_back")
        .where(col(Revision.user_message_seq) >= user_message_seq)
        .order_by(col(Revision.user_message_seq).asc(), col(Revision.created_at).asc())
    )
    return list(result.scalars().all())


async def latest_active_agent_revision_before_seq(
    session: AsyncSession,
    agent_session_id: str,
    user_message_seq: int,
) -> Revision | None:
    """Return the latest non-rolled-back agent revision before the given seq."""
    result = await session.execute(
        select(Revision)
        .where(col(Revision.agent_session_id) == agent_session_id)
        .where(col(Revision.revision_type) == "agent")
        .where(col(Revision.status) != "rolled_back")
        .where(col(Revision.user_message_seq) < user_message_seq)
        .order_by(col(Revision.user_message_seq).desc(), col(Revision.created_at).desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def count_by_project(
    session: AsyncSession,
    project_id: str,
    only_checkpoints: bool = False,
) -> int:
    """
    Mengambil jumlah total versi sebuah proyek.

    Args:
        session: session basis data.
        project_id: ID proyek.
        only_checkpoints: Apakah hanya menghitung checkpoint.

    Returns:
        Jumlah total versi.
    """
    query = select(func.count(col(Revision.id))).where(
        col(Revision.project_id) == project_id
    )

    if only_checkpoints:
        query = query.where(col(Revision.is_checkpoint))

    result = await session.execute(query)
    return result.scalar_one()


async def update(session: AsyncSession, revision: Revision) -> Revision:
    """
    Memperbarui versi.

    Args:
        session: session basis data.
        revision: Instance versi.

    Returns:
        Instance versi setelah diperbarui.
    """
    session.add(revision)
    await session.flush()
    await session.refresh(revision)
    return revision


async def delete(session: AsyncSession, revision: Revision) -> None:
    """
    Menghapus versi.

    Args:
        session: session basis data.
        revision: Instance versi.
    """
    await session.delete(revision)
    await session.flush()


async def delete_by_project(session: AsyncSession, project_id: str) -> None:
    """
    Menghapus semua versi dalam proyek.

    Args:
        session: session basis data.
        project_id: ID proyek.
    """
    from sqlalchemy import delete as sql_delete

    await session.execute(
        sql_delete(Revision).where(col(Revision.project_id) == project_id)
    )
    await session.flush()


async def update_status(
    session: AsyncSession,
    revision_id: str,
    status: str,
) -> Revision | None:
    """
    Memperbarui status versi.

    Args:
        session: session basis data.
        revision_id: ID versi.
        status: Status baru (active/completed).

    Returns:
        Instance versi setelah diperbarui, atau None bila tidak ada.
    """
    revision = await get_by_id(session, revision_id)
    if revision:
        revision.status = status
        revision.updated_at = datetime.now(UTC)
        if status in {"completed", "interrupted", "failed", "cancelled", "rollback", "rolled_back"}:
            revision.finished_at = datetime.now(UTC)
        session.add(revision)
        await session.flush()
        await session.refresh(revision)
    return revision


async def cancel_active_or_interrupted_revision(
    session: AsyncSession,
    revision_id: str,
) -> bool:
    """Atomically cancel a revision that is still resumable."""
    from sqlalchemy import update as sql_update

    now = datetime.now(UTC)
    result = await session.execute(
        sql_update(Revision)
        .where(col(Revision.id) == revision_id)
        .where(col(Revision.status).in_(("active", "interrupted")))
        .values(status="cancelled", finished_at=now, updated_at=now)
    )
    await session.flush()
    return cast("CursorResult[Any]", result).rowcount == 1


async def update_status_unless_cancelled(
    session: AsyncSession,
    revision_id: str,
    status: str,
) -> bool:
    """Update a revision without overwriting a committed cancellation."""
    from sqlalchemy import update as sql_update

    now = datetime.now(UTC)
    values: dict[str, Any] = {
        "status": status,
        "updated_at": now,
    }
    if status in {"completed", "interrupted", "failed", "rollback", "rolled_back"}:
        values["finished_at"] = now

    result = await session.execute(
        sql_update(Revision)
        .where(col(Revision.id) == revision_id)
        .where(col(Revision.status) != "cancelled")
        .values(**values)
    )
    await session.flush()
    return cast("CursorResult[Any]", result).rowcount == 1


async def claim_interrupted_revision(session: AsyncSession, revision_id: str) -> bool:
    """Atomically mark an interrupted revision active for a single resume."""
    from sqlalchemy import update as sql_update

    result = await session.execute(
        sql_update(Revision)
        .where(col(Revision.id) == revision_id)
        .where(col(Revision.status) == "interrupted")
        .values(status="active", finished_at=None, updated_at=datetime.now(UTC))
    )
    await session.flush()
    return cast("CursorResult[Any]", result).rowcount == 1


async def recover_failed_revision(session: AsyncSession, revision_id: str) -> bool:
    """Restore a failed revision when its checkpoint still contains an interrupt."""
    from sqlalchemy import update as sql_update

    now = datetime.now(UTC)
    result = await session.execute(
        sql_update(Revision)
        .where(col(Revision.id) == revision_id)
        .where(col(Revision.status) == "failed")
        .values(status="interrupted", finished_at=now, updated_at=now)
    )
    await session.flush()
    return cast("CursorResult[Any]", result).rowcount == 1


async def release_active_revision_claim(session: AsyncSession, revision_id: str) -> bool:
    """Return a failed resume launch to its interrupted state without reviving a cancel."""
    from sqlalchemy import update as sql_update

    now = datetime.now(UTC)
    result = await session.execute(
        sql_update(Revision)
        .where(col(Revision.id) == revision_id)
        .where(col(Revision.status) == "active")
        .values(status="interrupted", finished_at=now, updated_at=now)
    )
    await session.flush()
    return cast("CursorResult[Any]", result).rowcount == 1


async def recover_active_revisions_for_stopped_tasks(session: AsyncSession) -> int:
    """Return orphaned active revisions to a resumable interrupted state."""
    from sqlalchemy import update as sql_update

    from app.storage.models.task import Task

    now = datetime.now(UTC)
    result = await session.execute(
        sql_update(Revision)
        .where(col(Revision.status) == "active")
        .where(
            col(Revision.task_id).in_(
                select(col(Task.id)).where(col(Task.is_running).is_(False))
            )
        )
        .values(status="interrupted", finished_at=now, updated_at=now)
    )
    await session.flush()
    return cast("CursorResult[Any]", result).rowcount


async def complete_active_revisions_by_session(
    session: AsyncSession,
    agent_session_id: str,
) -> int:
    """
    Menandai semua versi aktif pada sesi tertentu sebagai selesai.

    Args:
        session: session basis data.
        agent_session_id: ID sesi Agent.

    Returns:
        Jumlah catatan yang diperbarui.
    """
    from sqlalchemy import update as sql_update

    result = await session.execute(
        sql_update(Revision)
        .where(col(Revision.agent_session_id) == agent_session_id)
        .where(col(Revision.status) == "active")
        .values(status="completed", finished_at=datetime.now(UTC), updated_at=datetime.now(UTC))
    )
    await session.flush()
    return cast("CursorResult[Any]", result).rowcount
