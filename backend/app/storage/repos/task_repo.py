# -*- coding: utf-8 -*-
"""
Task Repository - lapisan akses data tugas.
"""

from datetime import UTC, datetime

from sqlalchemy import delete as sql_delete
from sqlalchemy import func, select, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.task import Task


async def add_token_usage(
    session: AsyncSession,
    task_id: str,
    *,
    token_input: int,
    token_output: int,
    token_cache: int,
    cost: float,
) -> Task | None:
    """Menambah akumulasi token dan biaya tugas.

    Masukan panggilan ini juga dicatat sebagai pemakaian konteks.
    """
    task = await get_by_id(session, task_id)
    if task is None:
        return None

    task.token_input += max(token_input, 0)
    task.token_output += max(token_output, 0)
    task.token_cache += max(token_cache, 0)
    task.context_input_tokens = max(token_input, 0)
    task.cost += max(cost, 0.0)
    session.add(task)
    await session.flush()
    await session.refresh(task)
    return task


async def create(session: AsyncSession, task: Task) -> Task:
    """
    Membuat tugas.

    Args:
        session: session basis data.
        task: Instance tugas.

    Returns:
        Instance tugas setelah dibuat.
    """
    session.add(task)
    await session.flush()
    await session.refresh(task)
    return task


async def get_by_id(session: AsyncSession, task_id: str) -> Task | None:
    """
    Mengambil tugas berdasarkan ID.

    Args:
        session: session basis data.
        task_id: ID tugas.

    Returns:
        Instance tugas, atau None bila tidak ada.
    """
    result = await session.execute(select(Task).where(col(Task.id) == task_id))
    return result.scalar_one_or_none()


async def get_by_agent_session_id(
    session: AsyncSession, agent_session_id: str
) -> Task | None:
    """Mengambil tugas berdasarkan Agent session ID."""
    result = await session.execute(
        select(Task).where(col(Task.agent_session_id) == agent_session_id)
    )
    return result.scalar_one_or_none()


async def list_by_project(
    session: AsyncSession,
    project_id: str,
    limit: int | None = None,
    offset: int = 0,
    search_query: str | None = None,
    favorited_only: bool = False,
) -> list[Task]:
    """
    Mengambil daftar tugas dalam proyek.

    Args:
        session: session basis data.
        project_id: ID proyek.
        limit: Batas jumlah hasil.
        offset: Offset.
        search_query: Kata kunci pencarian (mencari berdasarkan judul).
        favorited_only: Apakah hanya mengembalikan tugas yang difavoritkan.

    Returns:
        Daftar tugas, urut waktu pembaruan menurun.
    """
    query = select(Task).where(col(Task.project_id) == project_id)

    if search_query:
        query = query.where(col(Task.title).contains(search_query))

    if favorited_only:
        query = query.where(col(Task.is_favorited))

    query = query.order_by(col(Task.updated_at).desc())

    if limit is not None:
        query = query.limit(limit)

    if offset > 0:
        query = query.offset(offset)

    result = await session.execute(query)
    return list(result.scalars().all())


async def count_by_project(
    session: AsyncSession,
    project_id: str,
    search_query: str | None = None,
    favorited_only: bool = False,
) -> int:
    """
    Mengambil jumlah total tugas dalam proyek.

    Args:
        session: session basis data.
        project_id: ID proyek.
        search_query: Kata kunci pencarian (mencari berdasarkan judul).
        favorited_only: Apakah hanya mengembalikan tugas yang difavoritkan.

    Returns:
        Jumlah total tugas.
    """
    query = select(func.count(col(Task.id))).where(col(Task.project_id) == project_id)

    if search_query:
        query = query.where(col(Task.title).contains(search_query))

    if favorited_only:
        query = query.where(col(Task.is_favorited))

    result = await session.execute(query)
    return result.scalar_one()


async def update_task(session: AsyncSession, task: Task) -> Task:
    """
    Memperbarui tugas.

    Args:
        session: session basis data.
        task: Instance tugas.

    Returns:
        Instance tugas setelah diperbarui.
    """
    session.add(task)
    await session.flush()
    await session.refresh(task)
    return task


async def clear_running_tasks(session: AsyncSession) -> int:
    """Mereset semua tugas yang sedang berjalan menjadi tidak berjalan."""
    result = await session.execute(
        sql_update(Task)
        .where(col(Task.is_running))
        .values(
            is_running=False,
            updated_at=datetime.now(UTC),
        )
    )
    await session.flush()
    return int(getattr(result, "rowcount", 0) or 0)


async def delete(session: AsyncSession, task: Task) -> None:
    """
    Menghapus tugas.

    Args:
        session: session basis data.
        task: Instance tugas.
    """
    await session.delete(task)
    await session.flush()


async def delete_by_project(session: AsyncSession, project_id: str) -> None:
    """
    Menghapus semua tugas dalam proyek.

    Args:
        session: session basis data.
        project_id: ID proyek.
    """
    await session.execute(sql_delete(Task).where(col(Task.project_id) == project_id))
    await session.flush()
