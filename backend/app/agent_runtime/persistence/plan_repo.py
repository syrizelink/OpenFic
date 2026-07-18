"""Shared plan repository helpers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.agent_runtime.persistence.model import PlanRecord, PlanTodoRecord


async def create_plan(session: AsyncSession, plan: PlanRecord) -> PlanRecord:
    session.add(plan)
    await session.flush()
    await session.refresh(plan)
    return plan


async def get_plan_by_session(session: AsyncSession, session_id: str) -> PlanRecord | None:
    result = await session.execute(
        select(PlanRecord)
        .where(col(PlanRecord.session_id) == session_id)
    )
    return result.scalar_one_or_none()


async def list_todos_by_plan(session: AsyncSession, plan_id: str) -> list[PlanTodoRecord]:
    result = await session.execute(
        select(PlanTodoRecord)
        .where(col(PlanTodoRecord.plan_id) == plan_id)
        .order_by(col(PlanTodoRecord.sort_index).asc(), col(PlanTodoRecord.id).asc())
    )
    return list(result.scalars().all())


async def replace_plan_todos(
    session: AsyncSession,
    *,
    plan_id: str,
    todos: list[PlanTodoRecord],
) -> list[PlanTodoRecord]:
    existing_rows = await list_todos_by_plan(session, plan_id)
    for row in existing_rows:
        await session.delete(row)

    await session.flush()

    for index, todo in enumerate(todos):
        todo.plan_id = plan_id
        todo.sort_index = index
        session.add(todo)

    await session.flush()
    persisted = await list_todos_by_plan(session, plan_id)
    for row in persisted:
        await session.refresh(row)
    return persisted
