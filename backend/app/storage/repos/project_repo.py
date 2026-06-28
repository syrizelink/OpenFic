# -*- coding: utf-8 -*-
"""
Project Repository - 项目数据访问层。
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.project import Project


async def create(session: AsyncSession, project: Project) -> Project:
    """
    创建项目。

    Args:
        session: 数据库 session。
        project: 项目实例。

    Returns:
        创建后的项目实例。
    """
    session.add(project)
    await session.flush()
    await session.refresh(project)
    return project


async def get_by_id(session: AsyncSession, project_id: str) -> Project | None:
    """
    根据 ID 获取项目。

    Args:
        session: 数据库 session。
        project_id: 项目 ID。

    Returns:
        项目实例，如果不存在则返回 None。
    """
    result = await session.execute(select(Project).where(col(Project.id) == project_id))
    return result.scalar_one_or_none()


async def list_all(
    session: AsyncSession,
    offset: int = 0,
    limit: int = 20,
) -> list[Project]:
    """
    获取项目列表。

    Args:
        session: 数据库 session。
        offset: 偏移量。
        limit: 每页数量。

    Returns:
        项目列表。
    """
    result = await session.execute(
        select(Project)
        .order_by(col(Project.updated_at).desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def count(session: AsyncSession) -> int:
    """
    获取项目总数。

    Args:
        session: 数据库 session。

    Returns:
        项目总数。
    """
    result = await session.execute(select(func.count(col(Project.id))))
    return result.scalar_one()


async def update(session: AsyncSession, project: Project) -> Project:
    """
    更新项目。

    Args:
        session: 数据库 session。
        project: 项目实例。

    Returns:
        更新后的项目实例。
    """
    session.add(project)
    await session.flush()
    await session.refresh(project)
    return project


async def delete(session: AsyncSession, project: Project) -> None:
    """
    删除项目。

    Args:
        session: 数据库 session。
        project: 项目实例。
    """
    await session.delete(project)
    await session.flush()
