# -*- coding: utf-8 -*-
"""
Task Service - 任务业务逻辑层。
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.agent_runtime.attachments import delete_attachments_for_task
from app.agent_runtime.modes import AgentMode
from app.agent_runtime.persistence.model import (
    AgentAttachment,
    AgentChildRun,
    AgentChildRunRequest,
    AgentContextCompaction,
    AgentRunMessage,
    PlanRecord,
    PlanTodoRecord,
)
from app.core.errors import NotFoundError
from app.storage.models.task import Task
from app.storage.models.task_message import TaskMessage
from app.storage.repos import project_repo, task_message_repo, task_repo
from app.storage.services.revision_service import delete_revision_data_by_tasks


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
    cost: float = 0.0,
) -> Task:
    """累加任务 token 和费用统计，并保留最近一次上下文输入占用。"""
    task = await task_repo.add_token_usage(
        session,
        task_id,
        token_input=token_input,
        token_output=token_output,
        token_cache=token_cache,
        cost=cost,
    )
    if task is None:
        raise NotFoundError(f"任务不存在：{task_id}")
    return task


async def delete_task(session: AsyncSession, task_id: str) -> None:
    """删除任务。"""
    task = await task_repo.get_by_id(session, task_id)
    if task is None:
        raise NotFoundError(f"任务不存在：{task_id}")

    await _delete_runtime_data_for_tasks(session, [task])
    await delete_revision_data_by_tasks(session, [task_id])
    await task_repo.delete(session, task)


async def delete_all_tasks(session: AsyncSession, project_id: str) -> int:
    """删除项目下的所有任务。"""
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"项目不存在：{project_id}")

    tasks = await task_repo.list_by_project(session, project_id)
    await _delete_runtime_data_for_tasks(session, tasks)
    await delete_revision_data_by_tasks(session, [task.id for task in tasks])
    await task_repo.delete_by_project(session, project_id)
    return len(tasks)


async def cleanup_orphaned_task_data(session: AsyncSession) -> int:
    """Delete runtime records whose owning Task has already been deleted."""
    existing_task_ids = select(col(Task.id))
    orphan_task_ids = await _list_orphan_task_ids(session, existing_task_ids)
    orphan_plan_session_ids = await _list_orphan_plan_session_ids(
        session,
        existing_task_ids,
    )
    orphan_child_run_ids = select(col(AgentChildRun.id)).where(
        col(AgentChildRun.parent_task_id).not_in(existing_task_ids)
    )
    deleted_rows = 0
    for task_id in orphan_task_ids:
        deleted_rows += await delete_attachments_for_task(session, task_id=task_id)
    request_result = await session.execute(
        delete(AgentChildRunRequest).where(
            col(AgentChildRunRequest.parent_task_id).not_in(existing_task_ids)
            | col(AgentChildRunRequest.child_run_id).in_(orphan_child_run_ids)
        )
    )
    deleted_rows += int(getattr(request_result, "rowcount", 0) or 0)
    for model, task_column in (
        (TaskMessage, TaskMessage.task_id),
        (AgentRunMessage, AgentRunMessage.task_id),
        (AgentContextCompaction, AgentContextCompaction.task_id),
        (AgentChildRun, AgentChildRun.parent_task_id),
    ):
        result = await session.execute(
            delete(model).where(col(task_column).not_in(existing_task_ids))
        )
        deleted_rows += int(getattr(result, "rowcount", 0) or 0)
    deleted_rows += await _delete_plans_for_sessions(session, orphan_plan_session_ids)
    await session.flush()
    return deleted_rows


async def _delete_runtime_data_for_tasks(
    session: AsyncSession,
    tasks: list[Task],
) -> None:
    task_ids = [task.id for task in tasks]
    if not task_ids:
        return
    session_ids = [
        task.agent_session_id
        for task in tasks
        if task.agent_session_id
    ]
    child_session_result = await session.execute(
        select(col(AgentChildRun.child_thread_id)).where(
            col(AgentChildRun.parent_task_id).in_(task_ids)
        )
    )
    session_ids.extend(
        child_thread_id
        for child_thread_id in child_session_result.scalars().all()
        if child_thread_id
    )
    await session.execute(
        delete(AgentChildRunRequest).where(
            col(AgentChildRunRequest.parent_task_id).in_(task_ids)
        )
    )
    await session.execute(
        delete(AgentChildRun).where(col(AgentChildRun.parent_task_id).in_(task_ids))
    )
    await session.execute(
        delete(AgentContextCompaction).where(
            col(AgentContextCompaction.task_id).in_(task_ids)
        )
    )
    await session.execute(
        delete(AgentRunMessage).where(col(AgentRunMessage.task_id).in_(task_ids))
    )
    await task_message_repo.delete_by_task_ids(session, task_ids)
    await _delete_plans_for_sessions(session, session_ids)
    await session.flush()


async def _delete_plans_for_sessions(
    session: AsyncSession,
    session_ids: list[str],
) -> int:
    if not session_ids:
        return 0
    plan_ids = select(col(PlanRecord.id)).where(
        col(PlanRecord.session_id).in_(session_ids)
    )
    todo_result = await session.execute(
        delete(PlanTodoRecord).where(col(PlanTodoRecord.plan_id).in_(plan_ids))
    )
    plan_result = await session.execute(
        delete(PlanRecord).where(col(PlanRecord.session_id).in_(session_ids))
    )
    return int(getattr(todo_result, "rowcount", 0) or 0) + int(
        getattr(plan_result, "rowcount", 0) or 0
    )


async def _list_orphan_plan_session_ids(
    session: AsyncSession,
    existing_task_ids: Any,
) -> list[str]:
    root_session_result = await session.execute(
        select(col(Task.agent_session_id)).where(
            col(Task.agent_session_id).is_not(None),
            col(Task.agent_session_id) != "",
        )
    )
    reachable_session_ids = {
        session_id
        for session_id in root_session_result.scalars().all()
        if session_id
    }
    child_session_result = await session.execute(
        select(col(AgentChildRun.child_thread_id)).where(
            col(AgentChildRun.parent_task_id).in_(existing_task_ids)
        )
    )
    reachable_session_ids.update(
        session_id for session_id in child_session_result.scalars().all() if session_id
    )
    result = await session.execute(
        select(col(PlanRecord.session_id)).where(
            col(PlanRecord.session_id).not_in(reachable_session_ids)
        )
    )
    return [session_id for session_id in result.scalars().all() if session_id]


async def _list_orphan_task_ids(
    session: AsyncSession,
    existing_task_ids: Any,
) -> list[str]:
    task_ids: set[str] = set()
    for task_column in (
        AgentAttachment.task_id,
        TaskMessage.task_id,
        AgentRunMessage.task_id,
        AgentContextCompaction.task_id,
        AgentChildRun.parent_task_id,
        AgentChildRunRequest.parent_task_id,
    ):
        result = await session.execute(
            select(col(task_column)).where(col(task_column).not_in(existing_task_ids))
        )
        task_ids.update(task_id for task_id in result.scalars().all() if task_id)
    return list(task_ids)


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
