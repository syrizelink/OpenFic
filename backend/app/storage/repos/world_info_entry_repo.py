# -*- coding: utf-8 -*-
"""
WorldInfoEntry Repository - 世界书条目数据访问层。
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
    创建世界书条目。

    Args:
        session: 数据库 session。
        entry: 条目实例。

    Returns:
        创建后的条目实例。
    """
    session.add(entry)
    await session.flush()
    await session.refresh(entry)
    return entry


async def get_by_id(session: AsyncSession, entry_id: str) -> WorldInfoEntry | None:
    """
    根据 ID 获取条目。

    Args:
        session: 数据库 session。
        entry_id: 条目 ID。

    Returns:
        条目实例，如果不存在则返回 None。
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
    获取世界书的条目列表。

    Args:
        session: 数据库 session。
        world_info_id: 世界书 ID。
        offset: 偏移量。
        limit: 每页数量。

    Returns:
        条目列表，按 order 排序。
    """
    result = await session.execute(
        select(WorldInfoEntry)
        .where(col(WorldInfoEntry.world_info_id) == world_info_id)
        .order_by(col(WorldInfoEntry.order))
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def list_enabled_by_world_info(
    session: AsyncSession,
    world_info_id: str,
) -> list[WorldInfoEntry]:
    """获取世界书内启用条目，按 order 排序。"""
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
    获取世界书的条目总数。

    Args:
        session: 数据库 session。
        world_info_id: 世界书 ID。

    Returns:
        条目总数。
    """
    result = await session.execute(
        select(func.count(col(WorldInfoEntry.id))).where(
            col(WorldInfoEntry.world_info_id) == world_info_id
        )
    )
    return result.scalar_one()


async def get_max_uid(session: AsyncSession, world_info_id: str) -> int:
    """
    获取世界书内的最大 UID。

    Args:
        session: 数据库 session。
        world_info_id: 世界书 ID。

    Returns:
        最大 UID，如果没有条目则返回 0。
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
    获取世界书内的最大排序序号。

    Args:
        session: 数据库 session。
        world_info_id: 世界书 ID。

    Returns:
        最大排序序号，如果没有条目则返回 0。
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
    更新条目。

    Args:
        session: 数据库 session。
        entry: 条目实例。

    Returns:
        更新后的条目实例。
    """
    session.add(entry)
    await session.flush()
    await session.refresh(entry)
    return entry


async def delete(session: AsyncSession, entry: WorldInfoEntry) -> None:
    """
    删除条目。

    Args:
        session: 数据库 session。
        entry: 条目实例。
    """
    await session.delete(entry)
    await session.flush()


async def delete_by_world_info(session: AsyncSession, world_info_id: str) -> None:
    """
    删除世界书的所有条目。

    Args:
        session: 数据库 session。
        world_info_id: 世界书 ID。
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
    """批量切换条目启用状态。"""
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
    """批量删除条目。"""
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
