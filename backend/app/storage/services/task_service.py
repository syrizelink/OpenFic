# -*- coding: utf-8 -*-
"""
Task Service - 任务业务逻辑层。
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.modes import AgentMode
from app.core.errors import NotFoundError
from app.storage.models.task import Task
from app.storage.models.task_message import TaskMessage
from app.storage.repos import project_repo, task_message_repo, task_repo


@dataclass
class TaskListResult:
    """任务列表结果。"""

    items: list[Task]
    total: int


async def create_task(
    session: AsyncSession,
    project_id: str,
    title: str,
    mode: AgentMode = "agent",
    agent_session_id: str | None = None,
) -> Task:
    """创建任务。"""
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"项目不存在：{project_id}")

    task = Task(
        project_id=project_id,
        title=title,
        mode=mode,
        agent_session_id=agent_session_id,
    )
    return await task_repo.create(session, task)


async def get_task(session: AsyncSession, task_id: str) -> Task:
    """获取任务。"""
    task = await task_repo.get_by_id(session, task_id)
    if task is None:
        raise NotFoundError(f"任务不存在：{task_id}")
    return task


async def get_task_by_agent_session_id(
    session: AsyncSession, agent_session_id: str
) -> Task:
    """根据 Agent 会话 ID 获取任务。"""
    task = await task_repo.get_by_agent_session_id(session, agent_session_id)
    if task is None:
        raise NotFoundError(f"会话不存在: {agent_session_id}")
    return task


async def list_tasks(
    session: AsyncSession,
    project_id: str,
    limit: int | None = None,
    offset: int = 0,
    search_query: str | None = None,
    favorited_only: bool = False,
) -> TaskListResult:
    """获取任务列表。"""
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"项目不存在：{project_id}")

    items = await task_repo.list_by_project(
        session,
        project_id,
        limit=limit,
        offset=offset,
        search_query=search_query,
        favorited_only=favorited_only,
    )

    total = await task_repo.count_by_project(
        session,
        project_id,
        search_query=search_query,
        favorited_only=favorited_only,
    )

    return TaskListResult(items=items, total=total)


async def update_task(
    session: AsyncSession,
    task_id: str,
    title: str | None = None,
    is_favorited: bool | None = None,
    is_running: bool | None = None,
    current_revision_id: str | None = None,
    current_message_id: str | None = None,
    agent_session_id: str | None = None,
) -> Task:
    """更新任务。"""
    task = await task_repo.get_by_id(session, task_id)
    if task is None:
        raise NotFoundError(f"任务不存在：{task_id}")

    if title is not None:
        task.title = title

    if is_favorited is not None:
        task.is_favorited = is_favorited

    if is_running is not None:
        task.is_running = is_running

    if current_revision_id is not None:
        task.current_revision_id = current_revision_id

    if current_message_id is not None:
        task.current_message_id = current_message_id

    if agent_session_id is not None:
        task.agent_session_id = agent_session_id

    task.updated_at = datetime.now(UTC)

    return await task_repo.update_task(session, task)


async def add_task_token_usage(
    session: AsyncSession,
    *,
    task_id: str,
    token_input: int,
    token_output: int,
    token_cache: int,
) -> Task:
    """累加任务 token 统计，并保留最近一次上下文输入占用。"""
    task = await task_repo.add_token_usage(
        session,
        task_id,
        token_input=token_input,
        token_output=token_output,
        token_cache=token_cache,
    )
    if task is None:
        raise NotFoundError(f"任务不存在：{task_id}")
    return task


async def delete_task(session: AsyncSession, task_id: str) -> None:
    """删除任务。"""
    task = await task_repo.get_by_id(session, task_id)
    if task is None:
        raise NotFoundError(f"任务不存在：{task_id}")

    await task_message_repo.delete_by_task(session, task.id)
    await task_repo.delete(session, task)


async def delete_all_tasks(session: AsyncSession, project_id: str) -> int:
    """删除项目下的所有任务。"""
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"项目不存在：{project_id}")

    total = await task_repo.count_by_project(session, project_id)
    tasks = await task_repo.list_by_project(session, project_id)
    for task in tasks:
        await task_message_repo.delete_by_task(session, task.id)
    await task_repo.delete_by_project(session, project_id)
    return total


async def clear_running_tasks(session: AsyncSession) -> int:
    """重置所有任务的运行状态。"""
    return await task_repo.clear_running_tasks(session)


async def list_task_messages(session: AsyncSession, task_id: str) -> list[TaskMessage]:
    task = await task_repo.get_by_id(session, task_id)
    if task is None:
        raise NotFoundError(f"任务不存在：{task_id}")
    return await task_message_repo.list_by_task(session, task_id)


async def append_task_message(
    session: AsyncSession,
    task_id: str,
    message: dict[str, Any],
) -> TaskMessage:
    task = await task_repo.get_by_id(session, task_id)
    if task is None:
        raise NotFoundError(f"任务不存在：{task_id}")

    task_message = TaskMessage(
        id=message["id"],
        task_id=task_id,
        role=message["role"],
        agent_id=message.get("agent_id"),
        content=message.get("content", ""),
        tool_calls=_dump_json(message.get("tool_calls", []), default="[]"),
        tool_call_id=message.get("tool_call_id"),
        message_metadata=_dump_json(message.get("metadata", {}), default="{}"),
        message_type=message.get("message_type"),
        message_status=message.get("message_status"),
        display_channel=message.get("display_channel"),
        payload=_dump_json(message.get("payload", {}), default="{}"),
        correlation_id=message.get("correlation_id"),
        created_at=message["created_at"],
        updated_at=message.get("updated_at", message["created_at"]),
    )
    return await task_message_repo.create(session, task_message)


def _dump_json(value: Any, default: str) -> str:
    import json

    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return default
