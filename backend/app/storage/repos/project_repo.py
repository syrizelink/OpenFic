# -*- coding: utf-8 -*-
"""
Project Repository - lapisan akses data proyek.
"""

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.project import Project

SORT_COLUMNS = {
    "updated_at": Project.updated_at,
    "created_at": Project.created_at,
    "title": Project.title,
}


def _escape_like_pattern(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _pinyin_search_pattern(search: str) -> str | None:
    compact_search = "".join(search.split())
    if not compact_search.isascii() or not compact_search.isalpha():
        return None
    return f"%{_escape_like_pattern(compact_search.lower())}%"


def _apply_search(stmt, search: str | None):
    normalized_search = (search or "").strip()
    if not normalized_search:
        return stmt

    pattern = f"%{_escape_like_pattern(normalized_search)}%"
    predicates = [
        col(Project.title).ilike(pattern, escape="\\"),
        col(Project.description).ilike(pattern, escape="\\"),
    ]
    pinyin_pattern = _pinyin_search_pattern(normalized_search)
    if pinyin_pattern:
        predicates.extend(
            (
                func.pinyin_full(col(Project.title)).like(pinyin_pattern, escape="\\"),
                func.pinyin_initials(col(Project.title)).like(pinyin_pattern, escape="\\"),
                func.pinyin_full(col(Project.description)).like(pinyin_pattern, escape="\\"),
                func.pinyin_initials(col(Project.description)).like(pinyin_pattern, escape="\\"),
            )
        )
    return stmt.where(or_(*predicates))


async def create(session: AsyncSession, project: Project) -> Project:
    """
    Membuat proyek.

    Args:
        session: session basis data.
        project: Instance proyek.

    Returns:
        Instance proyek setelah dibuat.
    """
    session.add(project)
    await session.flush()
    await session.refresh(project)
    return project


async def get_by_id(session: AsyncSession, project_id: str) -> Project | None:
    """
    Mengambil proyek berdasarkan ID.

    Args:
        session: session basis data.
        project_id: ID proyek.

    Returns:
        Instance proyek, atau None bila tidak ada.
    """
    result = await session.execute(select(Project).where(col(Project.id) == project_id))
    return result.scalar_one_or_none()


async def list_all(
    session: AsyncSession,
    offset: int = 0,
    limit: int = 20,
    *,
    search: str | None = None,
    sort_by: str = "updated_at",
    sort_order: str = "desc",
) -> list[Project]:
    """
    Mengambil daftar proyek.

    Args:
        session: session basis data.
        offset: Offset.
        limit: Jumlah per halaman.

    Returns:
        Daftar proyek.
    """
    sort_column = SORT_COLUMNS.get(sort_by, Project.updated_at)
    sortable_expression = (
        func.pinyin_full(col(Project.title)) if sort_by == "title" else col(sort_column)
    )
    order_expression = sortable_expression.asc() if sort_order == "asc" else sortable_expression.desc()
    stmt = (
        _apply_search(select(Project), search)
        .order_by(order_expression, col(Project.id).asc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count(session: AsyncSession, *, search: str | None = None) -> int:
    """
    Mengambil jumlah total proyek.

    Args:
        session: session basis data.

    Returns:
        Jumlah total proyek.
    """
    result = await session.execute(
        _apply_search(select(func.count(col(Project.id))), search)
    )
    return result.scalar_one()


async def update(session: AsyncSession, project: Project) -> Project:
    """
    Memperbarui proyek.

    Args:
        session: session basis data.
        project: Instance proyek.

    Returns:
        Instance proyek setelah diperbarui.
    """
    session.add(project)
    await session.flush()
    await session.refresh(project)
    return project


async def delete(session: AsyncSession, project: Project) -> None:
    """
    Menghapus proyek.

    Args:
        session: session basis data.
        project: Instance proyek.
    """
    await session.delete(project)
    await session.flush()
