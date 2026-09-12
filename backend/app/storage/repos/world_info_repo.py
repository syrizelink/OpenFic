# -*- coding: utf-8 -*-
"""
WorldInfo Repository - lapisan akses data buku dunia.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.world_info import WorldInfo


async def create(session: AsyncSession, world_info: WorldInfo) -> WorldInfo:
    """
    Membuat buku dunia.

    Args:
        session: session basis data.
        world_info: Instance buku dunia.

    Returns:
        Instance buku dunia setelah dibuat.
    """
    session.add(world_info)
    await session.flush()
    await session.refresh(world_info)
    return world_info


async def get_by_id(session: AsyncSession, world_info_id: str) -> WorldInfo | None:
    """
    Mengambil buku dunia berdasarkan ID.

    Args:
        session: session basis data.
        world_info_id: ID buku dunia.

    Returns:
        Instance buku dunia, atau None bila tidak ada.
    """
    result = await session.execute(
        select(WorldInfo).where(col(WorldInfo.id) == world_info_id)
    )
    return result.scalar_one_or_none()


async def get_by_project_id(session: AsyncSession, project_id: str) -> WorldInfo | None:
    """
    Mengambil buku dunia berdasarkan ID proyek.

    Args:
        session: session basis data.
        project_id: ID proyek.

    Returns:
        Instance buku dunia, atau None bila tidak ada.
    """
    result = await session.execute(
        select(WorldInfo).where(col(WorldInfo.project_id) == project_id)
    )
    return result.scalar_one_or_none()


async def get_all(
    session: AsyncSession,
    page: int = 1,
    page_size: int = 100,
) -> tuple[list[WorldInfo], int]:
    """
    Mengambil daftar semua buku dunia.

    Args:
        session: session basis data.
        page: Nomor halaman (mulai dari 1).
        page_size: Jumlah per halaman.

    Returns:
        Tuple (daftar buku dunia, jumlah total).
    """
    count_result = await session.execute(select(func.count(col(WorldInfo.id))))
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    result = await session.execute(
        select(WorldInfo)
        .order_by(col(WorldInfo.updated_at).desc())
        .offset(offset)
        .limit(page_size)
    )
    items = list(result.scalars().all())

    return items, total


async def update(session: AsyncSession, world_info: WorldInfo) -> WorldInfo:
    """
    Memperbarui buku dunia.

    Args:
        session: session basis data.
        world_info: Instance buku dunia.

    Returns:
        Instance buku dunia setelah diperbarui.
    """
    session.add(world_info)
    await session.flush()
    await session.refresh(world_info)
    return world_info


async def delete(session: AsyncSession, world_info: WorldInfo) -> None:
    """
    Menghapus buku dunia.

    Args:
        session: session basis data.
        world_info: Instance buku dunia.
    """
    await session.delete(world_info)
    await session.flush()


async def count(session: AsyncSession) -> int:
    """
    Mengambil jumlah total buku dunia.

    Args:
        session: session basis data.

    Returns:
        Jumlah total buku dunia.
    """
    result = await session.execute(select(func.count(col(WorldInfo.id))))
    return result.scalar_one()
