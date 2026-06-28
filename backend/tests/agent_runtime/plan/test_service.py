import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.plan import service as plan_service
from app.agent_runtime.tools.errors import ToolExecutionError


def _todo(title: str, content: str) -> dict[str, str]:
    return {"title": title, "content": content}


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
async def test_create_plan_uses_parent_session_scope_for_child_runtime(
    session: AsyncSession,
) -> None:
    root = await plan_service.create_plan(
        session,
        runtime_state=_state("parent-1"),
        topic="root",
        description="root",
        parent_dependency_todo_id=None,
        todos=[_todo("Root Todo", "root todo")],
    )

    child_view = await plan_service.list_plans(
        session,
        runtime_state=_state("child-1", parent_session_id="parent-1"),
    )

    assert [plan["id"] for plan in child_view] == [root["id"]]


@pytest.mark.asyncio
async def test_create_plan_rejects_dependency_to_non_root_plan(
    session: AsyncSession,
) -> None:
    root = await plan_service.create_plan(
        session,
        runtime_state=_state("parent-1"),
        topic="root",
        description="root",
        parent_dependency_todo_id=None,
        todos=[_todo("Root Todo", "root todo")],
    )
    child = await plan_service.create_plan(
        session,
        runtime_state=_state("parent-1"),
        topic="child",
        description="child",
        parent_dependency_todo_id=root["todos"][0]["id"],
        todos=[_todo("Child Todo", "child todo")],
    )

    with pytest.raises(ToolExecutionError, match="依赖目标必须是根计划的 Todo"):
        await plan_service.create_plan(
            session,
            runtime_state=_state("parent-1"),
            topic="grandchild",
            description="grandchild",
            parent_dependency_todo_id=child["todos"][0]["id"],
            todos=[_todo("Grandchild Todo", "grandchild todo")],
        )


@pytest.mark.asyncio
async def test_update_plan_uses_contiguous_slice_compare_and_swap(
    session: AsyncSession,
) -> None:
    plan = await plan_service.create_plan(
        session,
        runtime_state=_state("parent-1"),
        topic="rewrite",
        description="rewrite",
        parent_dependency_todo_id=None,
        todos=[
            _todo("Todo A", "a"),
            _todo("Todo B", "b"),
            _todo("Todo C", "c"),
        ],
    )

    updated = await plan_service.update_plan(
        session,
        runtime_state=_state("parent-1"),
        plan_id=plan["id"],
        old_todos=[plan["todos"][1]],
        new_todos=[{**plan["todos"][1], "status": "in_progress"}],
    )

    assert [todo["status"] for todo in updated["todos"]] == [
        "pending",
        "in_progress",
        "pending",
    ]
    assert [todo["title"] for todo in updated["todos"]] == [
        "Todo A",
        "Todo B",
        "Todo C",
    ]
    assert updated["status"] == "in_progress"

    with pytest.raises(ToolExecutionError, match="old_todos 与当前 Todo 列表不匹配"):
        await plan_service.update_plan(
            session,
            runtime_state=_state("parent-1"),
            plan_id=plan["id"],
            old_todos=[plan["todos"][0], plan["todos"][2]],
            new_todos=[],
        )


@pytest.mark.asyncio
async def test_update_plan_blocks_referenced_todo_content_change_and_deletion(
    session: AsyncSession,
) -> None:
    root = await plan_service.create_plan(
        session,
        runtime_state=_state("parent-1"),
        topic="root",
        description="root",
        parent_dependency_todo_id=None,
        todos=[_todo("Root Todo", "root todo")],
    )
    await plan_service.create_plan(
        session,
        runtime_state=_state("parent-1"),
        topic="child",
        description="child",
        parent_dependency_todo_id=root["todos"][0]["id"],
        todos=[_todo("Child Todo", "child todo")],
    )

    with pytest.raises(ToolExecutionError, match="该 Todo 已被其他计划依赖，不能删除或修改内容"):
        await plan_service.update_plan(
            session,
            runtime_state=_state("parent-1"),
            plan_id=root["id"],
            old_todos=[root["todos"][0]],
            new_todos=[{**root["todos"][0], "title": "Changed", "content": "changed"}],
        )

    with pytest.raises(ToolExecutionError, match="该 Todo 已被其他计划依赖，不能删除或修改内容"):
        await plan_service.update_plan(
            session,
            runtime_state=_state("parent-1"),
            plan_id=root["id"],
            old_todos=[root["todos"][0]],
            new_todos=[],
        )


@pytest.mark.asyncio
async def test_plan_status_becomes_completed_when_all_todos_complete(
    session: AsyncSession,
) -> None:
    plan = await plan_service.create_plan(
        session,
        runtime_state=_state("parent-1"),
        topic="rewrite",
        description="rewrite",
        parent_dependency_todo_id=None,
        todos=[_todo("Todo A", "a"), _todo("Todo B", "b")],
    )

    first = await plan_service.update_plan(
        session,
        runtime_state=_state("parent-1"),
        plan_id=plan["id"],
        old_todos=[plan["todos"][0]],
        new_todos=[{**plan["todos"][0], "status": "completed"}],
    )
    final = await plan_service.update_plan(
        session,
        runtime_state=_state("parent-1"),
        plan_id=plan["id"],
        old_todos=[first["todos"][1]],
        new_todos=[{**first["todos"][1], "status": "completed"}],
    )

    assert final["status"] == "completed"


@pytest.mark.asyncio
async def test_create_plan_rejects_cross_scope_and_fan_out_dependency(
    session: AsyncSession,
) -> None:
    root = await plan_service.create_plan(
        session,
        runtime_state=_state("parent-1"),
        topic="root",
        description="root",
        parent_dependency_todo_id=None,
        todos=[_todo("Root Todo", "root todo")],
    )

    with pytest.raises(ToolExecutionError, match="依赖目标必须位于当前会话作用域"):
        await plan_service.create_plan(
            session,
            runtime_state=_state("parent-2"),
            topic="other",
            description="other",
            parent_dependency_todo_id=root["todos"][0]["id"],
            todos=[_todo("Blocked Todo", "blocked")],
        )

    await plan_service.create_plan(
        session,
        runtime_state=_state("parent-1"),
        topic="child-1",
        description="child-1",
        parent_dependency_todo_id=root["todos"][0]["id"],
        todos=[_todo("Child Todo", "child todo")],
    )

    with pytest.raises(ToolExecutionError, match="该依赖目标已被其他计划占用"):
        await plan_service.create_plan(
            session,
            runtime_state=_state("parent-1"),
            topic="child-2",
            description="child-2",
            parent_dependency_todo_id=root["todos"][0]["id"],
            todos=[_todo("Child Todo", "child todo")],
        )


@pytest.mark.asyncio
async def test_update_plan_rejects_empty_final_plan_and_in_progress_delete_and_forces_new_todo_pending(
    session: AsyncSession,
) -> None:
    plan = await plan_service.create_plan(
        session,
        runtime_state=_state("parent-3"),
        topic="rewrite",
        description="rewrite",
        parent_dependency_todo_id=None,
        todos=[_todo("Todo A", "a"), _todo("Todo B", "b")],
    )

    with pytest.raises(ToolExecutionError, match="更新后计划不能为空"):
        await plan_service.update_plan(
            session,
            runtime_state=_state("parent-3"),
            plan_id=plan["id"],
            old_todos=plan["todos"],
            new_todos=[],
        )

    active = await plan_service.create_plan(
        session,
        runtime_state=_state("parent-4"),
        topic="active",
        description="active",
        parent_dependency_todo_id=None,
        todos=[_todo("Active Todo", "todo")],
    )
    active = await plan_service.update_plan(
        session,
        runtime_state=_state("parent-4"),
        plan_id=active["id"],
        old_todos=[active["todos"][0]],
        new_todos=[{**active["todos"][0], "status": "in_progress"}],
    )

    with pytest.raises(ToolExecutionError, match="进行中的 Todo 不可删除"):
        await plan_service.update_plan(
            session,
            runtime_state=_state("parent-4"),
            plan_id=active["id"],
            old_todos=[active["todos"][0]],
            new_todos=[],
        )

    updated = await plan_service.update_plan(
        session,
        runtime_state=_state("parent-3"),
        plan_id=plan["id"],
        old_todos=[plan["todos"][1]],
        new_todos=[
            {**plan["todos"][1], "status": "completed"},
            {"title": "New Todo", "content": "new todo", "status": "completed"},
        ],
    )

    assert updated["todos"][1]["status"] == "completed"
    assert updated["todos"][1]["title"] == "Todo B"
    assert updated["todos"][2]["title"] == "New Todo"
    assert updated["todos"][2]["content"] == "new todo"
    assert updated["todos"][2]["status"] == "pending"
