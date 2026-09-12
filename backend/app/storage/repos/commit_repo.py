# -*- coding: utf-8 -*-
"""
Commit Repository - lapisan akses data perubahan.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.commit import Commit
from app.storage.repos import revision_content_blob_repo


async def create(session: AsyncSession, commit: Commit) -> Commit:
    """
    Membuat catatan perubahan.

    Args:
        session: session basis data.
        commit: Instance perubahan.

    Returns:
        Instance perubahan setelah dibuat.
    """
    session.add(commit)
    await session.flush()
    await session.refresh(commit)
    return commit


async def _hydrate_commit(
    session: AsyncSession,
    commit: Commit | None,
) -> Commit | None:
    """Fill inline content columns from blob references (if any)."""
    if commit is None:
        return None
    await revision_content_blob_repo.hydrate_content(
        session,
        [commit],
        blob_id_attr="snapshot_content_blob_id",
        content_attr="snapshot_content",
    )
    await revision_content_blob_repo.hydrate_content(
        session,
        [commit],
        blob_id_attr="new_content_blob_id",
        content_attr="new_content",
    )
    return commit


async def _hydrate_commits(
    session: AsyncSession,
    commits: list[Commit],
) -> list[Commit]:
    await revision_content_blob_repo.hydrate_content(
        session,
        commits,
        blob_id_attr="snapshot_content_blob_id",
        content_attr="snapshot_content",
    )
    await revision_content_blob_repo.hydrate_content(
        session,
        commits,
        blob_id_attr="new_content_blob_id",
        content_attr="new_content",
    )
    return commits


async def get_by_id(session: AsyncSession, commit_id: str) -> Commit | None:
    """
    Mengambil catatan perubahan berdasarkan ID.

    Args:
        session: session basis data.
        commit_id: ID perubahan.

    Returns:
        Instance perubahan, atau None bila tidak ada.
    """
    result = await session.execute(select(Commit).where(col(Commit.id) == commit_id))
    return await _hydrate_commit(session, result.scalar_one_or_none())


async def list_by_revision(
    session: AsyncSession,
    revision_id: str,
) -> list[Commit]:
    """
    Mengambil semua catatan perubahan dalam sebuah versi.

    Args:
        session: session basis data.
        revision_id: ID versi.

    Returns:
        Daftar perubahan, diurutkan berdasarkan waktu pembuatan.
    """
    result = await session.execute(
        select(Commit)
        .where(col(Commit.revision_id) == revision_id)
        .order_by(col(Commit.created_at).asc())
    )
    return await _hydrate_commits(session, list(result.scalars().all()))


async def list_by_chapter(
    session: AsyncSession,
    chapter_id: str,
    offset: int = 0,
    limit: int = 50,
) -> list[Commit]:
    """
    Mengambil riwayat perubahan sebuah bab.

    Args:
        session: session basis data.
        chapter_id: ID bab.
        offset: Offset.
        limit: Jumlah per halaman.

    Returns:
        Daftar perubahan, urut waktu pembuatan menurun.
    """
    result = await session.execute(
        select(Commit)
        .where(col(Commit.chapter_id) == chapter_id)
        .order_by(col(Commit.created_at).desc())
        .offset(offset)
        .limit(limit)
    )
    return await _hydrate_commits(session, list(result.scalars().all()))


async def delete(session: AsyncSession, commit: Commit) -> None:
    """
    Menghapus catatan perubahan.

    Args:
        session: session basis data.
        commit: Instance perubahan.
    """
    await session.delete(commit)
    await session.flush()


async def delete_by_revision(session: AsyncSession, revision_id: str) -> None:
    """
    Menghapus semua catatan perubahan dalam sebuah versi.

    Args:
        session: session basis data.
        revision_id: ID versi.
    """
    from sqlalchemy import delete as sql_delete

    await session.execute(
        sql_delete(Commit).where(col(Commit.revision_id) == revision_id)
    )
    await session.flush()
