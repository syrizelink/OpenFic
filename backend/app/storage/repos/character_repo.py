# -*- coding: utf-8 -*-
"""Character Repository - lapisan akses data tokoh."""

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import delete as sql_delete
from sqlalchemy.engine import CursorResult
from sqlalchemy import func, or_, select
from sqlalchemy import update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.character import Character


async def create(session: AsyncSession, character: Character) -> Character:
    """Membuat tokoh."""
    session.add(character)
    await session.flush()
    await session.refresh(character)
    return character


async def get_by_id(session: AsyncSession, character_id: str) -> Character | None:
    """Mengambil tokoh berdasarkan ID."""
    result = await session.execute(
        select(Character).where(col(Character.id) == character_id)
    )
    return result.scalar_one_or_none()


async def list_names_by_project(session: AsyncSession, project_id: str) -> list[str]:
    """Mengambil semua nama tokoh dalam proyek."""
    result = await session.execute(
        select(col(Character.name)).where(col(Character.project_id) == project_id)
    )
    return list(result.scalars().all())


async def name_exists(
    session: AsyncSession,
    project_id: str,
    name: str,
    exclude_character_id: str | None = None,
) -> bool:
    """Memeriksa apakah nama tokoh sudah ada dalam proyek yang sama."""
    statement = select(col(Character.id)).where(
        col(Character.project_id) == project_id,
        col(Character.name) == name,
    )
    if exclude_character_id is not None:
        statement = statement.where(col(Character.id) != exclude_character_id)
    result = await session.execute(statement.limit(1))
    return result.scalar_one_or_none() is not None


async def list_by_project(
    session: AsyncSession,
    project_id: str,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Character], int]:
    """Mengambil daftar tokoh per proyek."""
    count_result = await session.execute(
        select(func.count(col(Character.id))).where(col(Character.project_id) == project_id)
    )
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    result = await session.execute(
        select(Character)
        .where(col(Character.project_id) == project_id)
        .order_by(col(Character.is_favorited).desc(), col(Character.updated_at).desc())
        .offset(offset)
        .limit(page_size)
    )
    return list(result.scalars().all()), total


async def list_all_by_project(session: AsyncSession, project_id: str) -> list[Character]:
    """Mengambil seluruh daftar tokoh per proyek."""
    result = await session.execute(
        select(Character)
        .where(col(Character.project_id) == project_id)
        .order_by(col(Character.is_favorited).desc(), col(Character.updated_at).desc())
    )
    return list(result.scalars().all())


async def update(session: AsyncSession, character: Character) -> Character:
    """Memperbarui tokoh."""
    session.add(character)
    await session.flush()
    await session.refresh(character)
    return character


async def search_by_project(session: AsyncSession, project_id: str, query: str) -> list[Character]:
    """Mencari nama dan deskripsi tokoh per proyek."""
    pattern = f"%{query}%"
    result = await session.execute(
        select(Character)
        .where(col(Character.project_id) == project_id)
        .where(or_(col(Character.name).ilike(pattern), col(Character.description).ilike(pattern)))
        .order_by(col(Character.is_favorited).desc(), col(Character.updated_at).desc())
    )
    return list(result.scalars().all())


async def list_by_project_and_ids(
    session: AsyncSession,
    project_id: str,
    character_ids: list[str],
) -> list[Character]:
    """Mengambil tokoh berdasarkan proyek dan daftar ID."""
    if not character_ids:
        return []
    result = await session.execute(
        select(Character).where(
            col(Character.project_id) == project_id,
            col(Character.id).in_(character_ids),
        )
    )
    return list(result.scalars().all())


async def batch_update_favorite(
    session: AsyncSession,
    project_id: str,
    character_ids: list[str],
    is_favorited: bool,
) -> int:
    """Memperbarui status favorit tokoh secara massal."""
    if not character_ids:
        return 0
    result = await session.execute(
        sql_update(Character)
        .where(
            col(Character.project_id) == project_id,
            col(Character.id).in_(character_ids),
        )
        .values(is_favorited=is_favorited, updated_at=datetime.now(UTC))
    )
    await session.flush()
    return cast("CursorResult[Any]", result).rowcount


async def batch_delete(
    session: AsyncSession,
    project_id: str,
    character_ids: list[str],
) -> int:
    """Menghapus tokoh secara massal."""
    if not character_ids:
        return 0
    result = await session.execute(
        sql_delete(Character).where(
            col(Character.project_id) == project_id,
            col(Character.id).in_(character_ids),
        )
    )
    await session.flush()
    return cast("CursorResult[Any]", result).rowcount


async def delete(session: AsyncSession, character: Character) -> None:
    """Menghapus tokoh."""
    await session.delete(character)
    await session.flush()
