# -*- coding: utf-8 -*-
"""
Commit Repository - 变更数据访问层。
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.commit import Commit


async def create(session: AsyncSession, commit: Commit) -> Commit:
    """
    创建变更记录。

    Args:
        session: 数据库 session。
        commit: 变更实例。

    Returns:
        创建后的变更实例。
    """
    session.add(commit)
    await session.flush()
    await session.refresh(commit)
    return commit


async def get_by_id(session: AsyncSession, commit_id: str) -> Commit | None:
    """
    根据 ID 获取变更记录。

    Args:
        session: 数据库 session。
        commit_id: 变更 ID。

    Returns:
        变更实例，如果不存在则返回 None。
    """
    result = await session.execute(select(Commit).where(col(Commit.id) == commit_id))
    return result.scalar_one_or_none()


async def list_by_revision(
    session: AsyncSession,
    revision_id: str,
) -> list[Commit]:
    """
    获取版本下的所有变更记录。

    Args:
        session: 数据库 session。
        revision_id: 版本 ID。

    Returns:
        变更列表，按创建时间排序。
    """
    result = await session.execute(
        select(Commit)
        .where(col(Commit.revision_id) == revision_id)
        .order_by(col(Commit.created_at).asc())
    )
    return list(result.scalars().all())


async def list_by_chapter(
    session: AsyncSession,
    chapter_id: str,
    offset: int = 0,
    limit: int = 50,
) -> list[Commit]:
    """
    获取章节的变更历史。

    Args:
        session: 数据库 session。
        chapter_id: 章节 ID。
        offset: 偏移量。
        limit: 每页数量。

    Returns:
        变更列表，按创建时间倒序。
    """
    result = await session.execute(
        select(Commit)
        .where(col(Commit.chapter_id) == chapter_id)
        .order_by(col(Commit.created_at).desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def delete(session: AsyncSession, commit: Commit) -> None:
    """
    删除变更记录。

    Args:
        session: 数据库 session。
        commit: 变更实例。
    """
    await session.delete(commit)
    await session.flush()


async def delete_by_revision(session: AsyncSession, revision_id: str) -> None:
    """
    删除版本下的所有变更记录。

    Args:
        session: 数据库 session。
        revision_id: 版本 ID。
    """
    from sqlalchemy import delete as sql_delete

    await session.execute(
        sql_delete(Commit).where(col(Commit.revision_id) == revision_id)
    )
    await session.flush()
