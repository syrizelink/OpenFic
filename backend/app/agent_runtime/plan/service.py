"""Business rules for shared PA/SA plan tools."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.persistence import plan_repo
from app.agent_runtime.persistence.model import PlanRecord, PlanTodoRecord
from app.agent_runtime.tools.errors import ToolExecutionError

PLAN_STATUSES = {"pending", "in_progress", "completed"}


def resolve_plan_scope_id(runtime_state: dict[str, Any]) -> str:
    scope_id = runtime_state.get("parent_session_id") or runtime_state.get("session_id")
    if not isinstance(scope_id, str) or not scope_id:
        raise ToolExecutionError("缺少计划作用域，无法访问共享计划")
    return scope_id


def derive_plan_status(todo_statuses: list[str]) -> str:
    if not todo_statuses:
        raise ToolExecutionError("计划必须至少包含一个 Todo")
    if all(status == "pending" for status in todo_statuses):
        return "pending"
    if all(status == "completed" for status in todo_statuses):
        return "completed"
    return "in_progress"


def _normalize_todo_title(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ToolExecutionError("Todo 标题不能为空")
    return value.strip()


def _normalize_todo_content(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ToolExecutionError("Todo 内容不能为空")
    return value.strip()


def _normalize_existing_todo_payload(payload: dict[str, Any]) -> dict[str, str]:
    todo_id = payload.get("id")
    title = payload.get("title")
    content = payload.get("content")
    status = payload.get("status")
    if not isinstance(todo_id, str) or not todo_id:
        raise ToolExecutionError("old_todos 与当前 Todo 列表不匹配")
    if not isinstance(title, str) or not title.strip():
        raise ToolExecutionError("old_todos 与当前 Todo 列表不匹配")
    if not isinstance(content, str) or not content.strip():
        raise ToolExecutionError("old_todos 与当前 Todo 列表不匹配")
    if status not in PLAN_STATUSES:
        raise ToolExecutionError("old_todos 与当前 Todo 列表不匹配")
    return {"id": todo_id, "title": title.strip(), "content": content.strip(), "status": status}


def _normalize_new_todo_payload(payload: dict[str, Any]) -> dict[str, str | None]:
    todo_id = payload.get("id")
    title = payload.get("title")
    content = payload.get("content")
    status = payload.get("status")
    if todo_id is not None and (not isinstance(todo_id, str) or not todo_id):
        raise ToolExecutionError("new_todos 中存在非法 Todo ID")
    if status is not None and status not in PLAN_STATUSES:
        raise ToolExecutionError("Todo 状态非法")
    return {
        "id": todo_id if isinstance(todo_id, str) else None,
        "title": _normalize_todo_title(title),
        "content": _normalize_todo_content(content),
        "status": status if isinstance(status, str) else None,
    }


def _normalize_create_todo_payload(payload: dict[str, Any]) -> dict[str, str]:
    return {
        "title": _normalize_todo_title(payload.get("title")),
        "content": _normalize_todo_content(payload.get("content")),
    }


def _serialize_plan_snapshot(
    plan: PlanRecord,
    todos: list[PlanTodoRecord],
) -> dict[str, Any]:
    return {
        "id": plan.id,
        "topic": plan.topic,
        "description": plan.description,
        "status": plan.status,
        "todos": [
            {
                "id": todo.id,
                "title": todo.title,
                "content": todo.content,
                "status": todo.status,
            }
            for todo in todos
        ],
    }


async def _serialize_plan_from_rows(
    session: AsyncSession,
    plan: PlanRecord,
    todos: list[PlanTodoRecord],
) -> dict[str, Any]:
    return _serialize_plan_snapshot(plan, todos)


def _ensure_plan_in_scope(plan: PlanRecord | None, scope_id: str) -> PlanRecord:
    if plan is None:
        raise ToolExecutionError("计划不存在")
    if plan.scope_id != scope_id:
        raise ToolExecutionError("计划不属于当前会话作用域")
    return plan


def _find_matching_slice(
    current_todos: list[PlanTodoRecord],
    old_todos: list[dict[str, str]],
) -> int:
    if not old_todos:
        raise ToolExecutionError("old_todos 与当前 Todo 列表不匹配")
    window = len(old_todos)
    for start in range(0, len(current_todos) - window + 1):
        candidate = current_todos[start : start + window]
        if all(
            row.id == payload["id"]
            and row.title == payload["title"]
            and row.content == payload["content"]
            and row.status == payload["status"]
            for row, payload in zip(candidate, old_todos, strict=True)
        ):
            return start
    raise ToolExecutionError("old_todos 与当前 Todo 列表不匹配")


def _ensure_valid_status(status: str) -> None:
    if status not in PLAN_STATUSES:
        raise ToolExecutionError("Todo 状态非法")


def _validate_existing_todo_update(
    current: PlanTodoRecord,
    *,
    new_title: str,
    new_content: str,
    new_status: str,
    is_referenced: bool,
) -> None:
    _ensure_valid_status(new_status)

    if current.status == "completed":
        if (
            new_title != current.title
            or new_content != current.content
            or new_status != current.status
        ):
            raise ToolExecutionError("已完成 Todo 不可修改")
        return

    if is_referenced and (new_title != current.title or new_content != current.content):
        raise ToolExecutionError("该 Todo 已被其他计划依赖，不能删除或修改内容")

    if is_referenced and current.status == "completed" and new_status != "completed":
        raise ToolExecutionError("该 Todo 已被其他计划依赖，不能删除或修改内容")


def _validate_todo_deletion(current: PlanTodoRecord, *, is_referenced: bool) -> None:
    if is_referenced:
        raise ToolExecutionError("该 Todo 已被其他计划依赖，不能删除或修改内容")
    if current.status == "in_progress":
        raise ToolExecutionError("进行中的 Todo 不可删除")
    if current.status == "completed":
        raise ToolExecutionError("已完成 Todo 不可修改")


async def create_plan(
    session: AsyncSession,
    *,
    runtime_state: dict[str, Any],
    topic: str,
    description: str,
    todos: list[dict[str, Any]],
) -> dict[str, Any]:
    if not todos:
        raise ToolExecutionError("计划必须至少包含一个 Todo")

    scope_id = resolve_plan_scope_id(runtime_state)

    now = datetime.now(UTC)
    plan = await plan_repo.create_plan(
        session,
        PlanRecord(
            scope_id=scope_id,
            topic=topic,
            description=description,
            status="pending",
            created_at=now,
            updated_at=now,
        ),
    )
    created_todos: list[PlanTodoRecord] = []
    for index, payload in enumerate(todos):
        normalized = _normalize_create_todo_payload(payload)
        created_todos.append(
            await plan_repo.create_plan_todo(
                session,
                PlanTodoRecord(
                    plan_id=plan.id,
                    title=normalized["title"],
                    content=normalized["content"],
                    status="pending",
                    sort_index=index,
                    created_at=now,
                    updated_at=now,
                ),
            )
        )

    plan.status = derive_plan_status([todo.status for todo in created_todos])
    plan.updated_at = now
    session.add(plan)
    await session.flush()
    await session.refresh(plan)
    return await _serialize_plan_from_rows(session, plan, created_todos)


async def update_plan(
    session: AsyncSession,
    *,
    runtime_state: dict[str, Any],
    plan_id: str,
    old_todos: list[dict[str, Any]],
    new_todos: list[dict[str, Any]],
) -> dict[str, Any]:
    scope_id = resolve_plan_scope_id(runtime_state)
    plan = _ensure_plan_in_scope(await plan_repo.get_plan(session, plan_id), scope_id)
    current_todos = await plan_repo.list_todos_by_plan(session, plan.id)
    normalized_old = [_normalize_existing_todo_payload(payload) for payload in old_todos]
    slice_start = _find_matching_slice(current_todos, normalized_old)
    slice_end = slice_start + len(normalized_old)
    current_slice = current_todos[slice_start:slice_end]
    current_slice_by_id = {todo.id: todo for todo in current_slice}

    normalized_new = [_normalize_new_todo_payload(payload) for payload in new_todos]
    retained_ids = {
        payload["id"]
        for payload in normalized_new
        if isinstance(payload.get("id"), str)
    }

    for payload in normalized_new:
        todo_id = payload["id"]
        title = str(payload["title"])
        content = str(payload["content"])
        if todo_id is None:
            continue
        current = current_slice_by_id.get(todo_id)
        if current is None:
            raise ToolExecutionError("old_todos 与当前 Todo 列表不匹配")
        status = payload["status"] or current.status
        _validate_existing_todo_update(
            current,
            new_title=title,
            new_content=content,
            new_status=status,
            is_referenced=False,
        )

    for todo in current_slice:
        if todo.id not in retained_ids:
            _validate_todo_deletion(todo, is_referenced=False)

    replacement_rows: list[PlanTodoRecord] = []
    now = datetime.now(UTC)
    for payload in normalized_new:
        todo_id = payload["id"]
        title = str(payload["title"])
        content = str(payload["content"])
        if todo_id is None:
            replacement_rows.append(
                PlanTodoRecord(
                    title=title,
                    content=content,
                    status="pending",
                    sort_index=0,
                    created_at=now,
                    updated_at=now,
                )
            )
            continue

        current = current_slice_by_id.get(todo_id)
        if current is None:
            raise ToolExecutionError("old_todos 与当前 Todo 列表不匹配")
        replacement_rows.append(
            PlanTodoRecord(
                id=current.id,
                plan_id=plan.id,
                title=title,
                content=content,
                status=payload["status"] or current.status,
                sort_index=0,
                created_at=current.created_at,
                updated_at=now,
            )
        )

    final_todos = [
        *[
            PlanTodoRecord(
                id=todo.id,
                plan_id=todo.plan_id,
                title=todo.title,
                content=todo.content,
                status=todo.status,
                sort_index=todo.sort_index,
                created_at=todo.created_at,
                updated_at=todo.updated_at,
            )
            for todo in current_todos[:slice_start]
        ],
        *replacement_rows,
        *[
            PlanTodoRecord(
                id=todo.id,
                plan_id=todo.plan_id,
                title=todo.title,
                content=todo.content,
                status=todo.status,
                sort_index=todo.sort_index,
                created_at=todo.created_at,
                updated_at=todo.updated_at,
            )
            for todo in current_todos[slice_end:]
        ],
    ]
    if not final_todos:
        raise ToolExecutionError("更新后计划不能为空")

    persisted_todos = await plan_repo.replace_plan_todos(
        session,
        plan_id=plan.id,
        todos=final_todos,
    )
    plan.status = derive_plan_status([todo.status for todo in persisted_todos])
    plan.updated_at = now
    session.add(plan)
    await session.flush()
    await session.refresh(plan)
    return await _serialize_plan_from_rows(session, plan, persisted_todos)


async def get_plan(
    session: AsyncSession,
    *,
    runtime_state: dict[str, Any],
    plan_id: str,
) -> dict[str, Any]:
    scope_id = resolve_plan_scope_id(runtime_state)
    plan = _ensure_plan_in_scope(await plan_repo.get_plan(session, plan_id), scope_id)
    todos = await plan_repo.list_todos_by_plan(session, plan.id)
    return await _serialize_plan_from_rows(session, plan, todos)


async def list_plans(
    session: AsyncSession,
    *,
    runtime_state: dict[str, Any],
) -> list[dict[str, Any]]:
    scope_id = resolve_plan_scope_id(runtime_state)
    plans = await plan_repo.list_plans_by_scope(session, scope_id)
    todos_by_plan = await plan_repo.list_todos_by_plan_ids(
        session,
        [plan.id for plan in plans],
    )
    snapshots: list[dict[str, Any]] = []
    for plan in plans:
        snapshots.append(
            await _serialize_plan_from_rows(
                session,
                plan,
                todos_by_plan.get(plan.id, []),
            )
        )
    return snapshots
