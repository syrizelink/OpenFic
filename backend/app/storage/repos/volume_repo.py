# -*- coding: utf-8 -*-
"""
Volume Repository - 卷数据访问层。
"""

from sqlalchemy import case, delete as sql_delete
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.volume import Volume


async def create(session: AsyncSession, volume: Volume) -> Volume:
    """创建卷。"""
    session.add(volume)
    await session.flush()
    await session.refresh(volume)
    return volume


async def get_by_id(session: AsyncSession, volume_id: str) -> Volume | None:
    """根据 ID 获取卷。"""
    result = await session.execute(select(Volume).where(col(Volume.id) == volume_id))
    return result.scalar_one_or_none()


async def list_by_project(session: AsyncSession, project_id: str) -> list[Volume]:
    """获取项目下的卷列表。"""
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
    """按标题搜索项目下的卷。"""
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
    """获取项目下卷数。"""
    result = await session.execute(
        select(func.count(col(Volume.id))).where(col(Volume.project_id) == project_id)
    )
    return result.scalar_one()


async def get_max_order(session: AsyncSession, project_id: str) -> int:
    """获取项目下最大卷序号。"""
    result = await session.execute(
        select(func.max(col(Volume.order))).where(col(Volume.project_id) == project_id)
    )
    max_order = result.scalar_one_or_none()
    return max_order if max_order is not None else 0


async def update_volume(session: AsyncSession, volume: Volume) -> Volume:
    """更新卷。"""
    session.add(volume)
    await session.flush()
    await session.refresh(volume)
    return volume


async def delete(session: AsyncSession, volume: Volume) -> None:
    """删除卷。"""
    await session.delete(volume)
    await session.flush()


async def delete_by_project(session: AsyncSession, project_id: str) -> None:
    """删除项目下所有卷。"""
    await session.execute(sql_delete(Volume).where(col(Volume.project_id) == project_id))
    await session.flush()


async def shift_orders(
    session: AsyncSession,
    project_id: str,
    start_order: int,
    end_order: int,
    delta: int,
) -> None:
    """批量调整项目内卷序号。"""
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
