from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.persistence import plan_repo
from app.agent_runtime.persistence.model import PlanRecord, PlanTodoRecord


@pytest.mark.asyncio
async def test_create_and_list_plan_todos_in_sort_order(db_session: AsyncSession) -> None:
    plan = await plan_repo.create_plan(
        db_session,
        PlanRecord(
            scope_id="scope-1",
            topic="rewrite",
            description="rewrite plan",
            status="pending",
        ),
    )
    await plan_repo.create_plan_todo(
        db_session,
        PlanTodoRecord(
            plan_id=plan.id,
            title="Beat 2",
            content="beat 2",
            status="pending",
            sort_index=1,
        ),
    )
    await plan_repo.create_plan_todo(
        db_session,
        PlanTodoRecord(
            plan_id=plan.id,
            title="Beat 1",
            content="beat 1",
            status="pending",
            sort_index=0,
        ),
    )
    await db_session.commit()

    todos = await plan_repo.list_todos_by_plan(db_session, plan.id)

    assert [todo.content for todo in todos] == ["beat 1", "beat 2"]
    assert [todo.title for todo in todos] == ["Beat 1", "Beat 2"]


@pytest.mark.asyncio
async def test_list_plans_by_scope_orders_by_created_at(db_session: AsyncSession) -> None:
    first = await plan_repo.create_plan(
        db_session,
        PlanRecord(
            scope_id="scope-1",
            topic="first",
            description="first",
            status="pending",
            created_at=datetime.now(UTC) - timedelta(minutes=1),
            updated_at=datetime.now(UTC) - timedelta(minutes=1),
        ),
    )
    second = await plan_repo.create_plan(
        db_session,
        PlanRecord(
            scope_id="scope-1",
            topic="second",
            description="second",
            status="pending",
        ),
    )
    await plan_repo.create_plan(
        db_session,
        PlanRecord(
            scope_id="scope-2",
            topic="other",
            description="other",
            status="pending",
        ),
    )
    await db_session.commit()

    plans = await plan_repo.list_plans_by_scope(db_session, "scope-1")

    assert [plan.id for plan in plans] == [first.id, second.id]

@pytest.mark.asyncio
async def test_replace_plan_todos_updates_existing_adds_new_and_deletes_removed(
    db_session: AsyncSession,
) -> None:
    plan = await plan_repo.create_plan(
        db_session,
        PlanRecord(scope_id="scope-1", topic="rewrite", description="rewrite", status="pending"),
    )
    first = await plan_repo.create_plan_todo(
        db_session,
        PlanTodoRecord(plan_id=plan.id, title="Todo A", content="a", status="pending", sort_index=0),
    )
    second = await plan_repo.create_plan_todo(
        db_session,
        PlanTodoRecord(plan_id=plan.id, title="Todo B", content="b", status="pending", sort_index=1),
    )
    await db_session.commit()

    persisted = await plan_repo.replace_plan_todos(
        db_session,
        plan_id=plan.id,
        todos=[
            PlanTodoRecord(
                id=second.id,
                plan_id=plan.id,
                title="Todo B Updated",
                content="b updated",
                status="in_progress",
                sort_index=0,
                created_at=second.created_at,
                updated_at=second.updated_at,
            ),
            PlanTodoRecord(
                plan_id=plan.id,
                title="Todo C",
                content="c",
                status="pending",
                sort_index=1,
            ),
        ],
    )
    await db_session.commit()

    assert len(persisted) == 2
    todos = await plan_repo.list_todos_by_plan(db_session, plan.id)
    assert [todo.content for todo in todos] == ["b updated", "c"]
    assert [todo.title for todo in todos] == ["Todo B Updated", "Todo C"]
    assert [todo.status for todo in todos] == ["in_progress", "pending"]
    assert all(todo.id != first.id for todo in todos)
