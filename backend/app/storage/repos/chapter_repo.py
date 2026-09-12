# -*- coding: utf-8 -*-
"""
Chapter Repository - lapisan akses data bab.
"""

from datetime import UTC, datetime
from typing import Any, Literal, NamedTuple, cast

from sqlalchemy import case, delete as sql_delete
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import QueryableAttribute, load_only
from sqlmodel import col

from app.storage.models.chapter import Chapter
from app.storage.models.volume import Volume


class ChapterIndexSource(NamedTuple):
    """Tampilan bab ringan untuk hitung status indeks, hanya id dan teks, agar tidak memuat seluruh baris."""

    project_id: str
    id: str
    content: str


def _chapter_metadata_attributes() -> tuple[QueryableAttribute[Any], ...]:
    return tuple(
        cast(QueryableAttribute[Any], attribute)
        for attribute in (
            Chapter.id,
            Chapter.project_id,
            Chapter.volume_id,
            Chapter.title,
            Chapter.word_count,
            Chapter.order,
            Chapter.created_at,
            Chapter.updated_at,
        )
    )


async def list_export_metadata_by_project(
    session: AsyncSession,
    project_id: str,
) -> list[tuple[str, str, str, int]]:
    """Membaca metadata bab dalam urutan ekspor, tanpa memuat teks."""
    result = await session.execute(
        select(
            col(Chapter.id),
            col(Chapter.volume_id),
            col(Chapter.title),
            col(Chapter.word_count),
        )
        .join(Volume, col(Chapter.volume_id) == col(Volume.id))
        .where(col(Chapter.project_id) == project_id)
        .order_by(col(Volume.order).asc(), col(Chapter.order).asc())
    )
    return [
        (chapter_id, volume_id, title, word_count)
        for chapter_id, volume_id, title, word_count in result.all()
    ]


async def create(session: AsyncSession, chapter: Chapter) -> Chapter:
    """
    Membuat bab.

    Args:
        session: session basis data.
        chapter: Instance bab.

    Returns:
        Instance bab setelah dibuat.
    """
    session.add(chapter)
    await session.flush()
    await session.refresh(chapter)
    return chapter


async def get_by_id(session: AsyncSession, chapter_id: str) -> Chapter | None:
    """
    Mengambil bab berdasarkan ID.

    Args:
        session: session basis data.
        chapter_id: ID bab.

    Returns:
        Instance bab, atau None bila tidak ada.
    """
    result = await session.execute(select(Chapter).where(col(Chapter.id) == chapter_id))
    return result.scalar_one_or_none()


async def get_by_ids(session: AsyncSession, chapter_ids: list[str]) -> list[Chapter]:
    """Mengambil bab secara massal berdasarkan daftar ID."""
    if not chapter_ids:
        return []
    result = await session.execute(
        select(Chapter).where(col(Chapter.id).in_(chapter_ids))
    )
    return list(result.scalars().all())


async def get_metadata_by_ids(session: AsyncSession, chapter_ids: list[str]) -> list[Chapter]:
    """Mengambil metadata bab berdasarkan daftar ID, tanpa memuat teks."""
    if not chapter_ids:
        return []
    result = await session.execute(
        select(Chapter)
        .options(load_only(*_chapter_metadata_attributes()))
        .where(col(Chapter.id).in_(chapter_ids))
    )
    return list(result.scalars().all())


async def list_by_project(
    session: AsyncSession,
    project_id: str,
) -> list[Chapter]:
    """
    Mengambil daftar semua bab dalam proyek.

    Args:
        session: session basis data.
        project_id: ID proyek.

    Returns:
        Daftar bab, diurutkan berdasarkan order.
    """
    result = await session.execute(
        select(Chapter)
        .join(Volume, col(Chapter.volume_id) == col(Volume.id))
        .where(col(Chapter.project_id) == project_id)
        .order_by(col(Volume.order).asc(), col(Chapter.order).asc())
    )
    return list(result.scalars().all())


async def list_metadata_by_project(
    session: AsyncSession,
    project_id: str,
) -> list[Chapter]:
    """Mengambil metadata bab proyek, tanpa memuat teks."""
    result = await session.execute(
        select(Chapter)
        .options(load_only(*_chapter_metadata_attributes()))
        .join(Volume, col(Chapter.volume_id) == col(Volume.id))
        .where(col(Chapter.project_id) == project_id)
        .order_by(col(Volume.order).asc(), col(Chapter.order).asc())
    )
    return list(result.scalars().all())


async def get_by_volume_ref(
    session: AsyncSession,
    volume_id: str,
    *,
    ref_type: Literal["order", "title"],
    ref_value: int | str,
) -> Chapter | None:
    """Mengambil satu bab berdasarkan nomor urut dalam volume atau judul."""
    stmt = select(Chapter).where(col(Chapter.volume_id) == volume_id)
    if ref_type == "order":
        stmt = stmt.where(col(Chapter.order) == int(ref_value))
    else:
        stmt = stmt.where(col(Chapter.title) == str(ref_value)).order_by(
            col(Chapter.order).asc()
        )
    result = await session.execute(stmt.limit(1))
    return result.scalar_one_or_none()


async def list_index_source_by_project(
    session: AsyncSession,
    project_id: str,
) -> list[ChapterIndexSource]:
    """Hanya membaca id dan teks bab untuk hitung status indeks, agar tidak memuat seluruh baris."""
    result = await session.execute(
        select(col(Chapter.id), col(Chapter.content))
        .join(Volume, col(Chapter.volume_id) == col(Volume.id))
        .where(col(Chapter.project_id) == project_id)
        .order_by(col(Volume.order).asc(), col(Chapter.order).asc())
    )
    return [
        ChapterIndexSource(project_id, chapter_id, content)
        for chapter_id, content in result.all()
    ]


async def list_index_source_by_projects(
    session: AsyncSession,
    project_ids: list[str],
) -> list[ChapterIndexSource]:
    """Membaca id dan teks bab dari beberapa proyek sekaligus untuk hitung status indeks keseluruhan."""
    if not project_ids:
        return []
    result = await session.execute(
        select(col(Chapter.project_id), col(Chapter.id), col(Chapter.content))
        .join(Volume, col(Chapter.volume_id) == col(Volume.id))
        .where(col(Chapter.project_id).in_(project_ids))
        .order_by(col(Volume.order).asc(), col(Chapter.order).asc())
    )
    return [
        ChapterIndexSource(project_id, chapter_id, content)
        for project_id, chapter_id, content in result.all()
    ]


async def search_with_volume_by_project(
    session: AsyncSession,
    project_id: str,
    query: str,
    *,
    limit: int,
) -> list[tuple[Chapter, Volume]]:
    """Mencari bab berdasarkan judul bab atau judul volume pemilik."""
    normalized_query = query.strip().lower()
    if not normalized_query:
        return []

    chapter_title_expr = func.lower(func.coalesce(col(Chapter.title), ""))
    volume_title_expr = func.lower(func.coalesce(col(Volume.title), ""))
    match_rank = case(
        (chapter_title_expr == normalized_query, 0),
        (chapter_title_expr.like(f"{normalized_query}%"), 1),
        (chapter_title_expr.contains(normalized_query), 2),
        (volume_title_expr == normalized_query, 3),
        (volume_title_expr.like(f"{normalized_query}%"), 4),
        else_=5,
    )

    result = await session.execute(
        select(Chapter, Volume)
        .join(Volume, col(Chapter.volume_id) == col(Volume.id))
        .where(
            col(Chapter.project_id) == project_id,
            or_(
                chapter_title_expr.contains(normalized_query),
                volume_title_expr.contains(normalized_query),
            ),
        )
        .order_by(
            match_rank.asc(),
            col(Volume.order).asc(),
            col(Chapter.order).asc(),
        )
        .limit(limit)
    )
    return [(chapter, volume) for chapter, volume in result.all()]


async def search_by_content(
    session: AsyncSession,
    project_id: str,
    query: str,
) -> list[tuple[Chapter, Volume]]:
    """Mencari bab berdasarkan isi, mengembalikan bab yang cocok beserta volume pemiliknya."""
    normalized_query = query.strip()
    if not normalized_query:
        return []

    result = await session.execute(
        select(Chapter, Volume)
        .join(Volume, col(Chapter.volume_id) == col(Volume.id))
        .where(
            col(Chapter.project_id) == project_id,
            col(Chapter.content).ilike(f"%{normalized_query}%"),
        )
        .order_by(col(Volume.order).asc(), col(Chapter.order).asc())
    )
    return [(chapter, volume) for chapter, volume in result.all()]


async def list_by_volume(
    session: AsyncSession,
    volume_id: str,
    *,
    offset: int = 0,
    limit: int | None = None,
) -> list[Chapter]:
    """Mengambil daftar bab dalam volume secara terpaginasi."""
    stmt = (
        select(Chapter)
        .where(col(Chapter.volume_id) == volume_id)
        .order_by(col(Chapter.order).asc())
        .offset(offset)
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_by_volume_from_order(
    session: AsyncSession,
    volume_id: str,
    start_order: int,
) -> list[Chapter]:
    """Membaca bab setelah nomor urut tertentu dalam volume.

    Menyegarkan status objek setelah pengurutan massal.
    """
    result = await session.execute(
        select(Chapter)
        .where(
            col(Chapter.volume_id) == volume_id,
            col(Chapter.order) >= start_order,
        )
        .order_by(col(Chapter.order).asc())
        .execution_options(populate_existing=True)
    )
    return list(result.scalars().all())


async def list_metadata_by_volume(
    session: AsyncSession,
    volume_id: str,
    *,
    offset: int = 0,
    limit: int | None = None,
) -> list[Chapter]:
    """Mengambil metadata bab dalam volume secara terpaginasi, tanpa memuat teks."""
    stmt = (
        select(Chapter)
        .options(load_only(*_chapter_metadata_attributes()))
        .where(col(Chapter.volume_id) == volume_id)
        .order_by(col(Chapter.order).asc())
        .offset(offset)
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_by_project_page(
    session: AsyncSession,
    project_id: str,
    *,
    offset: int,
    limit: int,
) -> list[Chapter]:
    """Mengambil daftar bab dalam proyek secara terpaginasi."""
    result = await session.execute(
        select(Chapter)
        .join(Volume, col(Chapter.volume_id) == col(Volume.id))
        .where(col(Chapter.project_id) == project_id)
        .order_by(col(Volume.order).asc(), col(Chapter.order).asc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def count_by_project(session: AsyncSession, project_id: str) -> int:
    """
    Mengambil jumlah total bab dalam proyek.

    Args:
        session: session basis data.
        project_id: ID proyek.

    Returns:
        Jumlah total bab.
    """
    result = await session.execute(
        select(func.count(col(Chapter.id))).where(col(Chapter.project_id) == project_id)
    )
    return result.scalar_one()


async def count_by_volume(session: AsyncSession, volume_id: str) -> int:
    """Mengambil jumlah total bab dalam volume."""
    result = await session.execute(
        select(func.count(col(Chapter.id))).where(col(Chapter.volume_id) == volume_id)
    )
    return result.scalar_one()


async def get_max_order(session: AsyncSession, volume_id: str) -> int:
    """
    Mengambil nomor urut terbesar dalam volume.

    Args:
        session: session basis data.
        volume_id: ID volume.

    Returns:
        Nomor urut terbesar, atau 0 bila tidak ada bab.
    """
    result = await session.execute(
        select(func.max(col(Chapter.order))).where(col(Chapter.volume_id) == volume_id)
    )
    max_order = result.scalar_one_or_none()
    return max_order if max_order is not None else 0


async def get_total_word_count(session: AsyncSession, project_id: str) -> int:
    """
    Mengambil total jumlah kata semua bab dalam proyek.

    Args:
        session: session basis data.
        project_id: ID proyek.

    Returns:
        Total jumlah kata.
    """
    result = await session.execute(
        select(func.sum(col(Chapter.word_count))).where(
            col(Chapter.project_id) == project_id
        )
    )
    total = result.scalar_one_or_none()
    return total if total is not None else 0


async def update_chapter(session: AsyncSession, chapter: Chapter) -> Chapter:
    """
    Memperbarui bab.

    Args:
        session: session basis data.
        chapter: Instance bab.

    Returns:
        Instance bab setelah diperbarui.
    """
    session.add(chapter)
    await session.flush()
    await session.refresh(chapter)
    return chapter


async def delete(session: AsyncSession, chapter: Chapter) -> None:
    """
    Menghapus bab.

    Args:
        session: session basis data.
        chapter: Instance bab.
    """
    await session.delete(chapter)
    await session.flush()


async def delete_by_volume(session: AsyncSession, volume_id: str) -> None:
    """Menghapus seluruh bab dalam volume."""
    await session.execute(
        sql_delete(Chapter).where(col(Chapter.volume_id) == volume_id)
    )
    await session.flush()


async def update_orders(
    session: AsyncSession,
    orders: dict[str, int],
) -> datetime | None:
    """
    Memperbarui urutan bab secara massal (dua tahap, menghindari konflik UNIQUE).

    Args:
        session: session basis data.
        orders: Pemetaan {chapter_id: new_order}.
    """
    if not orders:
        return None

    now = datetime.now(UTC)
    ids = list(orders.keys())

    # Phase 1: move orders to distinct negative values to avoid UNIQUE conflicts.
    await session.execute(
        update(Chapter)
        .where(col(Chapter.id).in_(ids))
        .values(
            order=-col(Chapter.order),
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    await session.flush()

    # Phase 2: use DBAPI executemany instead of a giant CASE expression.
    await session.execute(
        update(Chapter),
        [
            {"id": chapter_id, "order": chapter_order, "updated_at": now}
            for chapter_id, chapter_order in orders.items()
        ],
    )
    await session.flush()
    return now


async def shift_orders(
    session: AsyncSession,
    volume_id: str,
    start_order: int,
    end_order: int,
    delta: int,
) -> None:
    """
    Menyesuaikan nomor urut secara massal.

    Dipakai saat bab dipindahkan untuk menyesuaikan urutan bab lain.
    Pembaruan dua tahap menghindari konflik indeks unik.

    Args:
        session: session basis data.
        project_id: ID proyek.
        start_order: Nomor urut awal (inklusif).
        end_order: Nomor urut akhir (inklusif).
        delta: Besar penyesuaian (+1 atau -1).
    """
    result = await session.execute(
        select(Chapter).where(
            col(Chapter.volume_id) == volume_id,
            col(Chapter.order) >= start_order,
            col(Chapter.order) <= end_order,
        )
    )
    orders = {chapter.id: chapter.order + delta for chapter in result.scalars().all()}
    await update_orders(session, orders)


async def delete_by_project(session: AsyncSession, project_id: str) -> None:
    """
    Menghapus semua bab dalam proyek.

    Args:
        session: session basis data.
        project_id: ID proyek.
    """
    await session.execute(
        sql_delete(Chapter).where(col(Chapter.project_id) == project_id)
    )
    await session.flush()


async def get_by_project_and_order(
    session: AsyncSession,
    project_id: str,
    order: int,
) -> Chapter | None:
    """Mencari bab berdasarkan nomor urut datar di dalam proyek."""
    if order < 1:
        return None
    chapters = await list_by_project(session, project_id)
    if order > len(chapters):
        return None
    return chapters[order - 1]


async def get_by_volume_and_order(
    session: AsyncSession,
    volume_id: str,
    order: int,
) -> Chapter | None:
    """Mencari bab berdasarkan volume_id dan nomor urut bab dalam volume."""
    stmt = select(Chapter).where(
        col(Chapter.volume_id) == volume_id,
        col(Chapter.order) == order,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
