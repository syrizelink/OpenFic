# -*- coding: utf-8 -*-
"""
Setting Repository - lapisan akses data setelan.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.setting import Setting


async def get_all(session: AsyncSession) -> list[Setting]:
    """
    Mengambil semua setelan.

    Args:
        session: session basis data.

    Returns:
        Daftar setelan.
    """
    result = await session.execute(select(Setting))
    return list(result.scalars().all())


async def get_by_key(session: AsyncSession, key: str) -> Setting | None:
    """
    Mengambil setelan berdasarkan nama kunci.

    Args:
        session: session basis data.
        key: Nama kunci setelan.

    Returns:
        Instance setelan, atau None bila tidak ada.
    """
    result = await session.execute(select(Setting).where(col(Setting.key) == key))
    return result.scalar_one_or_none()


async def upsert(session: AsyncSession, key: str, value: str) -> Setting:
    """
    Membuat atau memperbarui setelan.

    Args:
        session: session basis data.
        key: Nama kunci setelan.
        value: Nilai setelan.

    Returns:
        Instance setelan.
    """
    existing = await get_by_key(session, key)
    if existing:
        existing.value = value
        existing.updated_at = datetime.now(UTC)
        session.add(existing)
        await session.flush()
        await session.refresh(existing)
        return existing
    else:
        setting = Setting(key=key, value=value)
        session.add(setting)
        await session.flush()
        await session.refresh(setting)
        return setting


async def bulk_upsert(session: AsyncSession, settings: dict[str, str]) -> list[Setting]:
    """
    Membuat atau memperbarui setelan secara massal.

    Args:
        session: session basis data.
        settings: Kamus pasangan kunci-nilai setelan.

    Returns:
        Daftar setelan setelah diperbarui.
    """
    result = []
    for key, value in settings.items():
        setting = await upsert(session, key, value)
        result.append(setting)
    return result
