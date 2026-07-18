import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.persistence import plan_repo
from app.agent_runtime.persistence.model import PlanRecord, PlanTodoRecord


@pytest.mark.asyncio
async def test_plan_records_are_unique_per_session(db_session: AsyncSession) -> None:
    await plan_repo.create_plan(db_session, PlanRecord(session_id="session-1"))
    await db_session.commit()

    with pytest.raises(IntegrityError):
        await plan_repo.create_plan(db_session, PlanRecord(session_id="session-1"))
    await db_session.rollback()


@pytest.mark.asyncio
async def test_replace_plan_todos_replaces_the_entire_ordered_list(
    db_session: AsyncSession,
) -> None:
    plan = await plan_repo.create_plan(db_session, PlanRecord(session_id="session-1"))
    db_session.add_all(
        [
            PlanTodoRecord(
                plan_id=plan.id,
                content="Old first",
                status="pending",
                priority="medium",
                sort_index=0,
            ),
            PlanTodoRecord(
                plan_id=plan.id,
                content="Old second",
                status="in_progress",
                priority="high",
                sort_index=1,
            ),
        ]
    )
    await db_session.commit()

    persisted = await plan_repo.replace_plan_todos(
        db_session,
        plan_id=plan.id,
        todos=[
            PlanTodoRecord(
                plan_id=plan.id,
                content="New only item",
                status="completed",
                priority="low",
                sort_index=0,
            )
        ],
    )

    assert [todo.content for todo in persisted] == ["New only item"]
    assert [todo.status for todo in persisted] == ["completed"]
    assert [todo.priority for todo in persisted] == ["low"]
