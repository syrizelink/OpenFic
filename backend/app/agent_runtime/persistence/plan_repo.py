"""Shared plan repository helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from collections.abc import Iterable

from sqlalchemy import delete as sql_delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.agent_runtime.persistence.model import PlanRecord, PlanTodoRecord


async def create_plan(session: AsyncSession, plan: PlanRecord) -> PlanRecord:
    session.add(plan)
    await session.flush()
    await session.refresh(plan)
    return plan


async def create_plan_todo(session: AsyncSession, todo: PlanTodoRecord) -> PlanTodoRecord:
    session.add(todo)
    await session.flush()
    await session.refresh(todo)
    return todo


async def get_plan(session: AsyncSession, plan_id: str) -> PlanRecord | None:
    return await session.get(PlanRecord, plan_id)


async def get_todo(session: AsyncSession, todo_id: str) -> PlanTodoRecord | None:
    return await session.get(PlanTodoRecord, todo_id)


async def get_plan_by_parent_dependency_id(
    session: AsyncSession,
    parent_dependency_id: str,
) -> PlanRecord | None:
    result = await session.execute(
        select(PlanRecord).where(
            col(PlanRecord.parent_dependency_id) == parent_dependency_id
        )
    )
    return result.scalar_one_or_none()


async def list_plans_by_scope(session: AsyncSession, scope_id: str) -> list[PlanRecord]:
    result = await session.execute(
        select(PlanRecord)
        .where(col(PlanRecord.scope_id) == scope_id)
        .order_by(col(PlanRecord.created_at).asc(), col(PlanRecord.id).asc())
    )
    return list(result.scalars().all())


async def list_todos_by_plan(session: AsyncSession, plan_id: str) -> list[PlanTodoRecord]:
    result = await session.execute(
        select(PlanTodoRecord)
        .where(col(PlanTodoRecord.plan_id) == plan_id)
        .order_by(col(PlanTodoRecord.sort_index).asc(), col(PlanTodoRecord.id).asc())
    )
    return list(result.scalars().all())


async def list_todos_by_plan_ids(
    session: AsyncSession,
    plan_ids: Iterable[str],
) -> dict[str, list[PlanTodoRecord]]:
    plan_id_list = list(plan_ids)
    if not plan_id_list:
        return {}
    result = await session.execute(
        select(PlanTodoRecord)
        .where(col(PlanTodoRecord.plan_id).in_(plan_id_list))
        .order_by(
            col(PlanTodoRecord.plan_id).asc(),
            col(PlanTodoRecord.sort_index).asc(),
            col(PlanTodoRecord.id).asc(),
        )
    )
    grouped: dict[str, list[PlanTodoRecord]] = {}
    for row in result.scalars().all():
        grouped.setdefault(row.plan_id, []).append(row)
    return grouped


async def list_referenced_todo_ids(session: AsyncSession, scope_id: str) -> set[str]:
    result = await session.execute(
        select(col(PlanRecord.parent_dependency_id)).where(
            col(PlanRecord.scope_id) == scope_id,
            col(PlanRecord.parent_dependency_id).is_not(None),
        )
    )
    return {todo_id for todo_id in result.scalars().all() if todo_id is not None}


async def delete_todos_by_ids(
    session: AsyncSession,
    *,
    plan_id: str,
    todo_ids: Iterable[str],
) -> int:
    todo_id_list = list(todo_ids)
    if not todo_id_list:
        return 0
    result = await session.execute(
        sql_delete(PlanTodoRecord).where(
            col(PlanTodoRecord.plan_id) == plan_id,
            col(PlanTodoRecord.id).in_(todo_id_list),
        )
    )
    await session.flush()
    return getattr(result, "rowcount", 0) or 0


async def replace_plan_todos(
    session: AsyncSession,
    *,
    plan_id: str,
    todos: list[PlanTodoRecord],
) -> list[PlanTodoRecord]:
    existing_rows = await list_todos_by_plan(session, plan_id)
    existing_by_id = {row.id: row for row in existing_rows}
    final_ids = {todo.id for todo in todos}
    now = datetime.now(UTC)

    for row in existing_rows:
        if row.id not in final_ids:
            await session.delete(row)

    await session.flush()

    keep_rows = [row for row in existing_rows if row.id in final_ids]
    for temp_index, row in enumerate(keep_rows):
        row.sort_index = -(temp_index + 1)
        row.updated_at = now
        session.add(row)

    await session.flush()

    for index, todo in enumerate(todos):
        existing_row = existing_by_id.get(todo.id)
        if existing_row is None:
            todo.plan_id = plan_id
            todo.sort_index = index
            todo.created_at = now
            todo.updated_at = now
            session.add(todo)
        else:
            existing_row.title = todo.title
            existing_row.content = todo.content
            existing_row.status = todo.status
            existing_row.sort_index = index
            existing_row.updated_at = now
            session.add(existing_row)

    await session.flush()
    persisted = await list_todos_by_plan(session, plan_id)
    for row in persisted:
        await session.refresh(row)
    return persisted
