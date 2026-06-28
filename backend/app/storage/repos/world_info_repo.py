# -*- coding: utf-8 -*-
"""
WorldInfo Repository - 世界书数据访问层。
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.world_info import WorldInfo


async def create(session: AsyncSession, world_info: WorldInfo) -> WorldInfo:
    """
    创建世界书。

    Args:
        session: 数据库 session。
        world_info: 世界书实例。

    Returns:
        创建后的世界书实例。
    """
    session.add(world_info)
    await session.flush()
    await session.refresh(world_info)
    return world_info


async def get_by_id(session: AsyncSession, world_info_id: str) -> WorldInfo | None:
    """
    根据 ID 获取世界书。

    Args:
        session: 数据库 session。
        world_info_id: 世界书 ID。

    Returns:
        世界书实例，如果不存在则返回 None。
    """
    result = await session.execute(
        select(WorldInfo).where(col(WorldInfo.id) == world_info_id)
    )
    return result.scalar_one_or_none()


async def get_by_project_id(session: AsyncSession, project_id: str) -> WorldInfo | None:
    """
    根据项目 ID 获取世界书。

    Args:
        session: 数据库 session。
        project_id: 项目 ID。

    Returns:
        世界书实例，如果不存在则返回 None。
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
    获取所有世界书列表。

    Args:
        session: 数据库 session。
        page: 页码（从 1 开始）。
        page_size: 每页数量。

    Returns:
        元组 (世界书列表, 总数)。
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
    更新世界书。

    Args:
        session: 数据库 session。
        world_info: 世界书实例。

    Returns:
        更新后的世界书实例。
    """
    session.add(world_info)
    await session.flush()
    await session.refresh(world_info)
    return world_info


async def delete(session: AsyncSession, world_info: WorldInfo) -> None:
    """
    删除世界书。

    Args:
        session: 数据库 session。
        world_info: 世界书实例。
    """
    await session.delete(world_info)
    await session.flush()


async def count(session: AsyncSession) -> int:
    """
    获取世界书总数。

    Args:
        session: 数据库 session。

    Returns:
        世界书总数。
    """
    result = await session.execute(select(func.count(col(WorldInfo.id))))
    return result.scalar_one()
