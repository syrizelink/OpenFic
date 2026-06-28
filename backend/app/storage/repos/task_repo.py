# -*- coding: utf-8 -*-
"""
Task Repository - 任务数据访问层。
"""

from datetime import UTC, datetime

from sqlalchemy import delete as sql_delete
from sqlalchemy import func, select, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.task import Task


async def add_token_usage(
    session: AsyncSession,
    task_id: str,
    *,
    token_input: int,
    token_output: int,
    token_cache: int,
) -> Task | None:
    """累加任务 token 统计，并记录本次调用输入 token 作为上下文占用。"""
    task = await get_by_id(session, task_id)
    if task is None:
        return None

    task.token_input += max(token_input, 0)
    task.token_output += max(token_output, 0)
    task.token_cache += max(token_cache, 0)
    task.context_input_tokens = max(token_input, 0)
    session.add(task)
    await session.flush()
    await session.refresh(task)
    return task


async def create(session: AsyncSession, task: Task) -> Task:
    """
    创建任务。

    Args:
        session: 数据库 session。
        task: 任务实例。

    Returns:
        创建后的任务实例。
    """
    session.add(task)
    await session.flush()
    await session.refresh(task)
    return task


async def get_by_id(session: AsyncSession, task_id: str) -> Task | None:
    """
    根据 ID 获取任务。

    Args:
        session: 数据库 session。
        task_id: 任务 ID。

    Returns:
        任务实例，如果不存在则返回 None。
    """
    result = await session.execute(select(Task).where(col(Task.id) == task_id))
    return result.scalar_one_or_none()


async def get_by_agent_session_id(
    session: AsyncSession, agent_session_id: str
) -> Task | None:
    """根据 Agent session ID 获取任务。"""
    result = await session.execute(
        select(Task).where(col(Task.agent_session_id) == agent_session_id)
    )
    return result.scalar_one_or_none()


async def list_by_project(
    session: AsyncSession,
    project_id: str,
    limit: int | None = None,
    offset: int = 0,
    search_query: str | None = None,
    favorited_only: bool = False,
) -> list[Task]:
    """
    获取项目下的任务列表。

    Args:
        session: 数据库 session。
        project_id: 项目 ID。
        limit: 返回数量限制。
        offset: 偏移量。
        search_query: 搜索关键词（按标题搜索）。
        favorited_only: 是否只返回收藏的任务。

    Returns:
        任务列表，按更新时间倒序排序。
    """
    query = select(Task).where(col(Task.project_id) == project_id)

    if search_query:
        query = query.where(col(Task.title).contains(search_query))

    if favorited_only:
        query = query.where(col(Task.is_favorited))

    query = query.order_by(col(Task.updated_at).desc())

    if limit is not None:
        query = query.limit(limit)

    if offset > 0:
        query = query.offset(offset)

    result = await session.execute(query)
    return list(result.scalars().all())


async def count_by_project(
    session: AsyncSession,
    project_id: str,
    search_query: str | None = None,
    favorited_only: bool = False,
) -> int:
    """
    获取项目下的任务总数。

    Args:
        session: 数据库 session。
        project_id: 项目 ID。
        search_query: 搜索关键词（按标题搜索）。
        favorited_only: 是否只返回收藏的任务。

    Returns:
        任务总数。
    """
    query = select(func.count(col(Task.id))).where(col(Task.project_id) == project_id)

    if search_query:
        query = query.where(col(Task.title).contains(search_query))

    if favorited_only:
        query = query.where(col(Task.is_favorited))

    result = await session.execute(query)
    return result.scalar_one()


async def update_task(session: AsyncSession, task: Task) -> Task:
    """
    更新任务。

    Args:
        session: 数据库 session。
        task: 任务实例。

    Returns:
        更新后的任务实例。
    """
    session.add(task)
    await session.flush()
    await session.refresh(task)
    return task


async def clear_running_tasks(session: AsyncSession) -> int:
    """将所有运行中的任务重置为非运行状态。"""
    result = await session.execute(
        sql_update(Task)
        .where(col(Task.is_running))
        .values(
            is_running=False,
            updated_at=datetime.now(UTC),
        )
    )
    await session.flush()
    return int(getattr(result, "rowcount", 0) or 0)


async def delete(session: AsyncSession, task: Task) -> None:
    """
    删除任务。

    Args:
        session: 数据库 session。
        task: 任务实例。
    """
    await session.delete(task)
    await session.flush()


async def delete_by_project(session: AsyncSession, project_id: str) -> None:
    """
    删除项目下的所有任务。

    Args:
        session: 数据库 session。
        project_id: 项目 ID。
    """
    await session.execute(sql_delete(Task).where(col(Task.project_id) == project_id))
    await session.flush()
