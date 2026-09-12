# -*- coding: utf-8 -*-
"""
WorldInfoEntry Repository - lapisan akses data entri buku dunia.
"""

from typing import Any, cast

from sqlalchemy import delete as sql_delete
from sqlalchemy.engine import CursorResult
from sqlalchemy import func, or_, select, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.world_info_entry import WorldInfoEntry


async def create(session: AsyncSession, entry: WorldInfoEntry) -> WorldInfoEntry:
    """
    Membuat entri buku dunia.

    Args:
        session: session basis data.
        entry: Instance entri.

    Returns:
        Instance entri setelah dibuat.
    """
    session.add(entry)
    await session.flush()
    await session.refresh(entry)
    return entry


async def get_by_id(session: AsyncSession, entry_id: str) -> WorldInfoEntry | None:
    """
    Mengambil entri berdasarkan ID.

    Args:
        session: session basis data.
        entry_id: ID entri.

    Returns:
        Instance entri, atau None bila tidak ada.
    """
    result = await session.execute(
        select(WorldInfoEntry).where(col(WorldInfoEntry.id) == entry_id)
    )
    return result.scalar_one_or_none()


async def list_by_world_info(
    session: AsyncSession,
    world_info_id: str,
    offset: int = 0,
    limit: int = 100,
) -> list[WorldInfoEntry]:
    """
    Mengambil daftar entri sebuah buku dunia.

    Args:
        session: session basis data.
        world_info_id: ID buku dunia.
        offset: Offset.
        limit: Jumlah per halaman.

    Returns:
        Daftar entri, diurutkan berdasarkan order.
    """
    result = await session.execute(
        select(WorldInfoEntry)
        .where(col(WorldInfoEntry.world_info_id) == world_info_id)
        .order_by(col(WorldInfoEntry.order))
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def list_all_by_world_info(
    session: AsyncSession,
    world_info_id: str,
) -> list[WorldInfoEntry]:
    """Mengambil seluruh daftar entri sebuah buku dunia."""
    result = await session.execute(
        select(WorldInfoEntry)
        .where(col(WorldInfoEntry.world_info_id) == world_info_id)
        .order_by(col(WorldInfoEntry.order))
    )
    return list(result.scalars().all())


async def list_enabled_by_world_info(
    session: AsyncSession,
    world_info_id: str,
) -> list[WorldInfoEntry]:
    """Mengambil entri aktif dalam buku dunia, diurutkan berdasarkan order."""
    result = await session.execute(
        select(WorldInfoEntry)
        .where(
            col(WorldInfoEntry.world_info_id) == world_info_id,
            col(WorldInfoEntry.is_enabled) == True,  # noqa: E712
        )
        .order_by(col(WorldInfoEntry.order))
    )
    return list(result.scalars().all())


async def search_by_world_info(
    session: AsyncSession,
    world_info_id: str,
    query: str,
    *,
    limit: int = 20,
) -> list[WorldInfoEntry]:
    pattern = f"%{query}%"
    result = await session.execute(
        select(WorldInfoEntry)
        .where(col(WorldInfoEntry.world_info_id) == world_info_id)
        .where(
            or_(
                col(WorldInfoEntry.name).ilike(pattern),
                col(WorldInfoEntry.content).ilike(pattern),
            )
        )
        .order_by(col(WorldInfoEntry.order))
        .limit(limit)
    )
    return list(result.scalars().all())


async def count_by_world_info(session: AsyncSession, world_info_id: str) -> int:
    """
    Mengambil jumlah total entri sebuah buku dunia.

    Args:
        session: session basis data.
        world_info_id: ID buku dunia.

    Returns:
        Jumlah total entri.
    """
    result = await session.execute(
        select(func.count(col(WorldInfoEntry.id))).where(
            col(WorldInfoEntry.world_info_id) == world_info_id
        )
    )
    return result.scalar_one()


async def get_max_uid(session: AsyncSession, world_info_id: str) -> int:
    """
    Mengambil UID terbesar dalam buku dunia.

    Args:
        session: session basis data.
        world_info_id: ID buku dunia.

    Returns:
        UID terbesar, atau 0 bila tidak ada entri.
    """
    result = await session.execute(
        select(func.max(col(WorldInfoEntry.uid))).where(
            col(WorldInfoEntry.world_info_id) == world_info_id
        )
    )
    max_uid = result.scalar_one_or_none()
    return max_uid if max_uid is not None else 0


async def get_max_order(session: AsyncSession, world_info_id: str) -> int:
    """
    Mengambil nomor urut terbesar dalam buku dunia.

    Args:
        session: session basis data.
        world_info_id: ID buku dunia.

    Returns:
        Nomor urut terbesar, atau 0 bila tidak ada entri.
    """
    result = await session.execute(
        select(func.max(col(WorldInfoEntry.order))).where(
            col(WorldInfoEntry.world_info_id) == world_info_id
        )
    )
    max_order = result.scalar_one_or_none()
    return max_order if max_order is not None else 0


async def update_entry(session: AsyncSession, entry: WorldInfoEntry) -> WorldInfoEntry:
    """
    Memperbarui entri.

    Args:
        session: session basis data.
        entry: Instance entri.

    Returns:
        Instance entri setelah diperbarui.
    """
    session.add(entry)
    await session.flush()
    await session.refresh(entry)
    return entry


async def delete(session: AsyncSession, entry: WorldInfoEntry) -> None:
    """
    Menghapus entri.

    Args:
        session: session basis data.
        entry: Instance entri.
    """
    await session.delete(entry)
    await session.flush()


async def delete_by_world_info(session: AsyncSession, world_info_id: str) -> None:
    """
    Menghapus semua entri sebuah buku dunia.

    Args:
        session: session basis data.
        world_info_id: ID buku dunia.
    """
    await session.execute(
        sql_delete(WorldInfoEntry).where(
            col(WorldInfoEntry.world_info_id) == world_info_id
        )
    )
    await session.flush()


async def batch_toggle(
    session: AsyncSession,
    world_info_id: str,
    entry_ids: list[str],
    is_enabled: bool,
) -> int:
    """Mengalihkan status aktif entri secara massal."""
    result = await session.execute(
        sql_update(WorldInfoEntry)
        .where(
            col(WorldInfoEntry.world_info_id) == world_info_id,
            col(WorldInfoEntry.id).in_(entry_ids),
        )
        .values(is_enabled=is_enabled)
    )
    await session.flush()
    return cast("CursorResult[Any]", result).rowcount


async def batch_delete(
    session: AsyncSession,
    world_info_id: str,
    entry_ids: list[str],
) -> int:
    """Menghapus entri secara massal."""
    result = await session.execute(
        sql_delete(WorldInfoEntry).where(
            col(WorldInfoEntry.world_info_id) == world_info_id,
            col(WorldInfoEntry.id).in_(entry_ids),
        )
    )
    await session.flush()
    return cast("CursorResult[Any]", result).rowcount


async def shift_orders(
    session: AsyncSession,
    world_info_id: str,
    start_order: int,
    end_order: int,
    delta: int,
) -> None:
    # ... existing shift_orders implementation remains unchanged
    await session.execute(
        sql_update(WorldInfoEntry)
        .where(
            col(WorldInfoEntry.world_info_id) == world_info_id,
            col(WorldInfoEntry.order) >= start_order,
            col(WorldInfoEntry.order) <= end_order,
        )
        .values(order=col(WorldInfoEntry.order) + delta)
    )
    await session.flush()


async def search_by_content(
    session: AsyncSession,
    world_info_id: str,
    query: str,
) -> list[WorldInfoEntry]:
    result = await session.execute(
        select(WorldInfoEntry)
        .where(
            col(WorldInfoEntry.world_info_id) == world_info_id,
            col(WorldInfoEntry.content).ilike(f"%{query}%"),
        )
        .order_by(col(WorldInfoEntry.order))
    )
    return list(result.scalars().all())
