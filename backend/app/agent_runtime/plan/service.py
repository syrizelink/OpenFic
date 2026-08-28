"""Business rules for the session-scoped plan tool."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.persistence import plan_repo
from app.agent_runtime.persistence.model import PlanRecord, PlanTodoRecord
from app.agent_runtime.tools.errors import ToolExecutionError

PLAN_STATUSES = {"pending", "in_progress", "completed"}
PLAN_PRIORITIES = {"low", "medium", "high"}


def format_plan_todos(todos: Sequence[Mapping[str, str]]) -> str:
    return "\n\n".join(
        f"[{index} {todo['status']} / {todo['priority']} priority]\n{todo['content']}"
        for index, todo in enumerate(todos, start=1)
    )


def format_current_plan(todos: Sequence[Mapping[str, str]]) -> str:
    return f"<current_plan>\n{format_plan_todos(todos)}\n</current_plan>"


def _resolve_session_id(runtime_state: dict[str, Any]) -> str:
    session_id = runtime_state.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        raise ToolExecutionError("缺少会话 ID，无法写入计划")
    return session_id


def _normalize_todo(payload: dict[str, Any]) -> dict[str, str]:
    content = payload.get("content")
    status = payload.get("status")
    priority = payload.get("priority")
    if not isinstance(content, str) or not content.strip():
        raise ToolExecutionError("Todo 内容不能为空")
    if status not in PLAN_STATUSES:
        raise ToolExecutionError("Todo 状态非法")
    if priority not in PLAN_PRIORITIES:
        raise ToolExecutionError("Todo 优先级非法")
    return {
        "content": content.strip(),
        "status": status,
        "priority": priority,
    }


def _serialize_todos(todos: list[PlanTodoRecord]) -> dict[str, list[dict[str, str]]]:
    return {
        "todos": _todo_payloads(todos),
    }


def _todo_payloads(todos: Sequence[PlanTodoRecord]) -> list[dict[str, str]]:
    return [
        {
            "content": todo.content,
            "status": todo.status,
            "priority": todo.priority,
        }
        for todo in todos
    ]


async def get_plan_todos(
    session: AsyncSession,
    session_id: str,
) -> list[dict[str, str]] | None:
    plan = await plan_repo.get_plan_by_session(session, session_id)
    if plan is None:
        return None
    return _todo_payloads(await plan_repo.list_todos_by_plan(session, plan.id))


async def write_plan(
    session: AsyncSession,
    *,
    runtime_state: dict[str, Any],
    todos: list[dict[str, Any]],
) -> dict[str, list[dict[str, str]]]:
    session_id = _resolve_session_id(runtime_state)
    plan = await plan_repo.get_plan_by_session(session, session_id)
    now = datetime.now(UTC)
    if plan is None:
        plan = await plan_repo.create_plan(
            session,
            PlanRecord(session_id=session_id, created_at=now, updated_at=now),
        )

    normalized_todos = [_normalize_todo(todo) for todo in todos]
    persisted_todos = await plan_repo.replace_plan_todos(
        session,
        plan_id=plan.id,
        todos=[
            PlanTodoRecord(
                plan_id=plan.id,
                content=todo["content"],
                status=todo["status"],
                priority=todo["priority"],
                sort_index=index,
                created_at=now,
                updated_at=now,
            )
            for index, todo in enumerate(normalized_todos)
        ],
    )
    plan.updated_at = now
    session.add(plan)
    await session.flush()
    await session.refresh(plan)
    return _serialize_todos(persisted_todos)
