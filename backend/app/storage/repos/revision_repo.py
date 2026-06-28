# -*- coding: utf-8 -*-
"""
Revision Repository - 版本数据访问层。
"""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.revision import Revision


async def create(session: AsyncSession, revision: Revision) -> Revision:
    """
    创建版本。

    Args:
        session: 数据库 session。
        revision: 版本实例。

    Returns:
        创建后的版本实例。
    """
    session.add(revision)
    await session.flush()
    await session.refresh(revision)
    return revision


async def get_by_id(session: AsyncSession, revision_id: str) -> Revision | None:
    """
    根据 ID 获取版本。

    Args:
        session: 数据库 session。
        revision_id: 版本 ID。

    Returns:
        版本实例，如果不存在则返回 None。
    """
    result = await session.execute(
        select(Revision).where(col(Revision.id) == revision_id)
    )
    return result.scalar_one_or_none()


async def list_by_project(
    session: AsyncSession,
    project_id: str,
    only_checkpoints: bool = False,
    offset: int = 0,
    limit: int = 50,
) -> list[Revision]:
    """
    获取项目的版本列表。

    Args:
        session: 数据库 session。
        project_id: 项目 ID。
        only_checkpoints: 是否只返回检查点。
        offset: 偏移量。
        limit: 每页数量。

    Returns:
        版本列表，按创建时间倒序。
    """
    query = select(Revision).where(col(Revision.project_id) == project_id)

    if only_checkpoints:
        query = query.where(col(Revision.is_checkpoint))

    query = query.order_by(col(Revision.created_at).desc()).offset(offset).limit(limit)

    result = await session.execute(query)
    return list(result.scalars().all())


async def list_by_agent_session_from_seq(
    session: AsyncSession,
    agent_session_id: str,
    user_message_seq: int,
) -> list[Revision]:
    """List non-rollback agent revisions from a user message seq onward."""
    result = await session.execute(
        select(Revision)
        .where(col(Revision.agent_session_id) == agent_session_id)
        .where(col(Revision.revision_type) == "agent")
        .where(col(Revision.status) != "rolled_back")
        .where(col(Revision.user_message_seq) >= user_message_seq)
        .order_by(col(Revision.user_message_seq).asc(), col(Revision.created_at).asc())
    )
    return list(result.scalars().all())


async def latest_active_agent_revision_before_seq(
    session: AsyncSession,
    agent_session_id: str,
    user_message_seq: int,
) -> Revision | None:
    """Return the latest non-rolled-back agent revision before the given seq."""
    result = await session.execute(
        select(Revision)
        .where(col(Revision.agent_session_id) == agent_session_id)
        .where(col(Revision.revision_type) == "agent")
        .where(col(Revision.status) != "rolled_back")
        .where(col(Revision.user_message_seq) < user_message_seq)
        .order_by(col(Revision.user_message_seq).desc(), col(Revision.created_at).desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def count_by_project(
    session: AsyncSession,
    project_id: str,
    only_checkpoints: bool = False,
) -> int:
    """
    获取项目的版本总数。

    Args:
        session: 数据库 session。
        project_id: 项目 ID。
        only_checkpoints: 是否只统计检查点。

    Returns:
        版本总数。
    """
    query = select(func.count(col(Revision.id))).where(
        col(Revision.project_id) == project_id
    )

    if only_checkpoints:
        query = query.where(col(Revision.is_checkpoint))

    result = await session.execute(query)
    return result.scalar_one()


async def update(session: AsyncSession, revision: Revision) -> Revision:
    """
    更新版本。

    Args:
        session: 数据库 session。
        revision: 版本实例。

    Returns:
        更新后的版本实例。
    """
    session.add(revision)
    await session.flush()
    await session.refresh(revision)
    return revision


async def delete(session: AsyncSession, revision: Revision) -> None:
    """
    删除版本。

    Args:
        session: 数据库 session。
        revision: 版本实例。
    """
    await session.delete(revision)
    await session.flush()


async def delete_by_project(session: AsyncSession, project_id: str) -> None:
    """
    删除项目下的所有版本。

    Args:
        session: 数据库 session。
        project_id: 项目 ID。
    """
    from sqlalchemy import delete as sql_delete

    await session.execute(
        sql_delete(Revision).where(col(Revision.project_id) == project_id)
    )
    await session.flush()


async def update_status(
    session: AsyncSession,
    revision_id: str,
    status: str,
) -> Revision | None:
    """
    更新版本状态。

    Args:
        session: 数据库 session。
        revision_id: 版本 ID。
        status: 新状态（active/completed）。

    Returns:
        更新后的版本实例，如果不存在则返回 None。
    """
    revision = await get_by_id(session, revision_id)
    if revision:
        revision.status = status
        revision.updated_at = datetime.now(UTC)
        if status in {"completed", "interrupted", "failed", "cancelled", "rollback", "rolled_back"}:
            revision.finished_at = datetime.now(UTC)
        session.add(revision)
        await session.flush()
        await session.refresh(revision)
    return revision


async def complete_active_revisions_by_session(
    session: AsyncSession,
    agent_session_id: str,
) -> int:
    """
    将指定会话的所有活跃版本标记为完成。

    Args:
        session: 数据库 session。
        agent_session_id: Agent 会话 ID。

    Returns:
        更新的记录数。
    """
    from sqlalchemy import update as sql_update

    result = await session.execute(
        sql_update(Revision)
        .where(col(Revision.agent_session_id) == agent_session_id)
        .where(col(Revision.status) == "active")
        .values(status="completed", finished_at=datetime.now(UTC), updated_at=datetime.now(UTC))
    )
    await session.flush()
    return result.rowcount  # type: ignore[attr-defined]
