import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.persistence import plan_repo
from app.agent_runtime.plan import service as plan_service


def _todo(content: str, status: str, priority: str) -> dict[str, str]:
    return {"content": content, "status": status, "priority": priority}


def _state(
    session_id: str = "session-1",
    *,
    parent_session_id: str | None = None,
) -> dict[str, str]:
    state = {"session_id": session_id}
    if parent_session_id is not None:
        state["parent_session_id"] = parent_session_id
    return state


@pytest.mark.asyncio
async def test_write_plan_replaces_the_complete_todo_list_in_one_session(
    session: AsyncSession,
) -> None:
    initial = await plan_service.write_plan(
        session,
        runtime_state=_state(),
        todos=[
            _todo("Inspect the outline", "pending", "medium"),
            _todo("Write the draft", "pending", "high"),
        ],
    )
    updated = await plan_service.write_plan(
        session,
        runtime_state=_state(),
        todos=[_todo("Review the draft", "in_progress", "high")],
    )

    assert initial["todos"] == [
        {"content": "Inspect the outline", "status": "pending", "priority": "medium"},
        {"content": "Write the draft", "status": "pending", "priority": "high"},
    ]
    assert updated == {
        "todos": [
            {
                "content": "Review the draft",
                "status": "in_progress",
                "priority": "high",
            }
        ]
    }
    plan = await plan_repo.get_plan_by_session(session, "session-1")
    assert plan is not None
    assert len(await plan_repo.list_todos_by_plan(session, plan.id)) == 1


@pytest.mark.asyncio
async def test_write_plan_is_isolated_to_the_current_session(
    session: AsyncSession,
) -> None:
    parent = await plan_service.write_plan(
        session,
        runtime_state=_state("parent-1"),
        todos=[_todo("Parent work", "pending", "medium")],
    )
    child = await plan_service.write_plan(
        session,
        runtime_state=_state("child-1", parent_session_id="parent-1"),
        todos=[_todo("Child work", "completed", "low")],
    )

    assert parent["todos"][0]["content"] == "Parent work"
    assert child["todos"][0]["content"] == "Child work"
    parent_plan = await plan_repo.get_plan_by_session(session, "parent-1")
    child_plan = await plan_repo.get_plan_by_session(session, "child-1")
    assert parent_plan is not None
    assert child_plan is not None
    assert parent_plan.id != child_plan.id


@pytest.mark.asyncio
async def test_write_plan_accepts_an_empty_complete_list(session: AsyncSession) -> None:
    await plan_service.write_plan(
        session,
        runtime_state=_state(),
        todos=[_todo("Completed work", "completed", "low")],
    )

    cleared = await plan_service.write_plan(session, runtime_state=_state(), todos=[])

    assert cleared == {"todos": []}
