# -*- coding: utf-8 -*-
"""
Setting Repository - 设置数据访问层。
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.setting import Setting


async def get_all(session: AsyncSession) -> list[Setting]:
    """
    获取所有设置。

    Args:
        session: 数据库 session。

    Returns:
        设置列表。
    """
    result = await session.execute(select(Setting))
    return list(result.scalars().all())


async def get_by_key(session: AsyncSession, key: str) -> Setting | None:
    """
    根据键名获取设置。

    Args:
        session: 数据库 session。
        key: 设置键名。

    Returns:
        设置实例，如果不存在则返回 None。
    """
    result = await session.execute(select(Setting).where(col(Setting.key) == key))
    return result.scalar_one_or_none()


async def upsert(session: AsyncSession, key: str, value: str) -> Setting:
    """
    创建或更新设置。

    Args:
        session: 数据库 session。
        key: 设置键名。
        value: 设置值。

    Returns:
        设置实例。
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
    批量创建或更新设置。

    Args:
        session: 数据库 session。
        settings: 设置键值对字典。

    Returns:
        更新后的设置列表。
    """
    result = []
    for key, value in settings.items():
        setting = await upsert(session, key, value)
        result.append(setting)
    return result
