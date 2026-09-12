# -*- coding: utf-8 -*-
"""
Volume Repository - lapisan akses data volume.
"""

from sqlalchemy import case, delete as sql_delete
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.volume import Volume


async def create(session: AsyncSession, volume: Volume) -> Volume:
    """Membuat volume."""
    session.add(volume)
    await session.flush()
    await session.refresh(volume)
    return volume


async def get_by_id(session: AsyncSession, volume_id: str) -> Volume | None:
    """Mengambil volume berdasarkan ID."""
    result = await session.execute(select(Volume).where(col(Volume.id) == volume_id))
    return result.scalar_one_or_none()


async def list_by_project(session: AsyncSession, project_id: str) -> list[Volume]:
    """Mengambil daftar volume dalam proyek."""
    result = await session.execute(
        select(Volume)
        .where(col(Volume.project_id) == project_id)
        .order_by(col(Volume.order).asc())
    )
    return list(result.scalars().all())


async def search_by_project(
    session: AsyncSession,
    project_id: str,
    query: str,
    *,
    limit: int,
) -> list[Volume]:
    """Mencari volume dalam proyek berdasarkan judul."""
    normalized_query = query.strip().lower()
    if not normalized_query:
        return []

    title_expr = func.lower(func.coalesce(col(Volume.title), ""))
    match_rank = case(
        (title_expr == normalized_query, 0),
        (title_expr.like(f"{normalized_query}%"), 1),
        else_=2,
    )

    result = await session.execute(
        select(Volume)
        .where(
            col(Volume.project_id) == project_id,
            title_expr.contains(normalized_query),
        )
        .order_by(match_rank.asc(), col(Volume.order).asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def count_by_project(session: AsyncSession, project_id: str) -> int:
    """Mengambil jumlah volume dalam proyek."""
    result = await session.execute(
        select(func.count(col(Volume.id))).where(col(Volume.project_id) == project_id)
    )
    return result.scalar_one()


async def get_max_order(session: AsyncSession, project_id: str) -> int:
    """Mengambil nomor urut volume terbesar dalam proyek."""
    result = await session.execute(
        select(func.max(col(Volume.order))).where(col(Volume.project_id) == project_id)
    )
    max_order = result.scalar_one_or_none()
    return max_order if max_order is not None else 0


async def update_volume(session: AsyncSession, volume: Volume) -> Volume:
    """Memperbarui volume."""
    session.add(volume)
    await session.flush()
    await session.refresh(volume)
    return volume


async def delete(session: AsyncSession, volume: Volume) -> None:
    """Menghapus volume."""
    await session.delete(volume)
    await session.flush()


async def delete_by_project(session: AsyncSession, project_id: str) -> None:
    """Menghapus semua volume dalam proyek."""
    await session.execute(sql_delete(Volume).where(col(Volume.project_id) == project_id))
    await session.flush()


async def shift_orders(
    session: AsyncSession,
    project_id: str,
    start_order: int,
    end_order: int,
    delta: int,
) -> None:
    """Menyesuaikan nomor urut volume dalam proyek secara massal."""
    await session.execute(
        update(Volume)
        .where(
            col(Volume.project_id) == project_id,
            col(Volume.order) >= start_order,
            col(Volume.order) <= end_order,
        )
        .values(order=col(Volume.order) + delta)
    )
    await session.flush()
