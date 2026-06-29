import importlib
import json
import sys
from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.agent_runtime.plan import service as plan_service
from app.agent_runtime.tools.registry import ToolRegistry


def _make_state() -> dict:
    return {
        "session_id": "session-1",
        "project_id": "project-1",
        "model_config": {},
        "active_agent": None,
        "is_completed": False,
        "error": None,
        "retry_count": 0,
        "user_request": "",
    }


def _reload_all_tool_impls() -> None:
    for module_name in list(sys.modules):
        if module_name.startswith("app.agent_runtime.tools.impls"):
            del sys.modules[module_name]
    importlib.import_module("app.agent_runtime.tools.impls")


@pytest.fixture(autouse=True)
def _restore_registry() -> Iterator[None]:
    original = dict(ToolRegistry._tools)
    try:
        yield
    finally:
        ToolRegistry._tools = original


def _fake_session():
    return SimpleNamespace(
        commit=AsyncMock(),
        rollback=AsyncMock(),
        close=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_create_plan_tool_uses_parent_session_scope() -> None:
    _reload_all_tool_impls()
    session = _fake_session()
    snapshot = {
        "id": "plan-1",
        "topic": "rewrite",
        "todos": [{"id": "todo-1", "title": "Todo A", "content": "a", "status": "pending"}],
        "status": "pending",
    }

    with patch(
        "app.agent_runtime.tools.impls.plan.create_plan.create_session",
        new=AsyncMock(return_value=session),
    ), patch(
        "app.agent_runtime.tools.impls.plan.create_plan.plan_service.create_plan",
        new=AsyncMock(return_value=snapshot),
    ) as create_plan_service:
        tool = ToolRegistry.get_tools(
            names=["create_plan"],
            state={
                **_make_state(),
                "task_id": "task-1",
                "active_agent": "composer",
                "parent_session_id": "parent-1",
            },
        )[0]
        result = await tool.ainvoke(
            {
                "topic": "rewrite",
                "description": "rewrite",
                "todos": [{"title": "Todo A", "content": "a"}],
            },
        )

    payload = json.loads(result)
    assert payload["success"] is True
    assert payload["plan"]["id"] == "plan-1"
    assert create_plan_service.await_args is not None
    assert create_plan_service.await_args.kwargs["runtime_state"]["parent_session_id"] == "parent-1"
    session.commit.assert_awaited_once()
    session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_plan_tool_returns_latest_snapshot() -> None:
    _reload_all_tool_impls()
    session = _fake_session()
    snapshot = {
        "id": "plan-1",
        "topic": "rewrite",
        "status": "in_progress",
        "todos": [{"id": "todo-1", "title": "Todo A", "content": "a", "status": "in_progress"}],
    }

    with patch(
        "app.agent_runtime.tools.impls.plan.update_plan.create_session",
        new=AsyncMock(return_value=session),
    ), patch(
        "app.agent_runtime.tools.impls.plan.update_plan.plan_service.update_plan",
        new=AsyncMock(return_value=snapshot),
    ):
        tool = ToolRegistry.get_tools(names=["update_plan"], state=_make_state())[0]
        result = await tool.ainvoke(
            {
                "plan_id": "plan-1",
                "old_todos": [{"id": "todo-1", "title": "Todo A", "content": "a", "status": "pending"}],
                "new_todos": [{"id": "todo-1", "title": "Todo A", "content": "a", "status": "in_progress"}],
            }
        )

    payload = json.loads(result)
    assert payload["message"] == "计划已更新"
    assert payload["plan"]["status"] == "in_progress"
    assert "parent_dependency" not in payload["plan"]
    assert payload["plan"]["todos"][0]["title"] == "Todo A"
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_plan_tool_returns_plan_payload() -> None:
    _reload_all_tool_impls()
    session = _fake_session()
    snapshot = {"id": "plan-1", "topic": "rewrite", "status": "pending", "todos": []}

    with patch(
        "app.agent_runtime.tools.impls.plan.get_plan.create_session",
        new=AsyncMock(return_value=session),
    ), patch(
        "app.agent_runtime.tools.impls.plan.get_plan.plan_service.get_plan",
        new=AsyncMock(return_value=snapshot),
    ):
        tool = ToolRegistry.get_tools(names=["get_plan"], state=_make_state())[0]
        result = await tool.ainvoke({"plan_id": "plan-1"})

    payload = json.loads(result)
    assert payload["success"] is True
    assert payload["plan"]["topic"] == "rewrite"
    session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_plan_tool_returns_plan_list() -> None:
    _reload_all_tool_impls()
    session = _fake_session()
    snapshots = [{"id": "plan-1", "topic": "rewrite", "status": "pending", "todos": []}]

    with patch(
        "app.agent_runtime.tools.impls.plan.list_plan.create_session",
        new=AsyncMock(return_value=session),
    ), patch(
        "app.agent_runtime.tools.impls.plan.list_plan.plan_service.list_plans",
        new=AsyncMock(return_value=snapshots),
    ):
        tool = ToolRegistry.get_tools(names=["list_plan"], state=_make_state())[0]
        result = await tool.ainvoke({})

    payload = json.loads(result)
    assert payload["success"] is True
    assert payload["plans"][0]["id"] == "plan-1"
    session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_plan_tool_accepts_structured_todo_inputs_through_real_schema(session) -> None:
    _reload_all_tool_impls()

    with patch(
        "app.agent_runtime.tools.impls.plan.create_plan.create_session",
        new=AsyncMock(return_value=session),
    ):
        tool = ToolRegistry.get_tools(
            names=["create_plan"],
            state={
                **_make_state(),
                "task_id": "task-1",
                "active_agent": "composer",
                "parent_session_id": "parent-1",
            },
        )[0]
        result = await tool.ainvoke(
            {
                "topic": "rewrite",
                "description": "rewrite",
                "todos": [{"title": "Todo A", "content": "a"}],
            }
        )

    payload = json.loads(result)
    assert payload["success"] is True
    assert payload["plan"]["todos"][0]["title"] == "Todo A"
    assert payload["plan"]["todos"][0]["content"] == "a"


@pytest.mark.asyncio
async def test_update_plan_tool_accepts_structured_todo_inputs_through_real_schema(session) -> None:
    _reload_all_tool_impls()
    plan = await plan_service.create_plan(
        session,
        runtime_state={"session_id": "session-1"},
        topic="rewrite",
        description="rewrite",
        todos=[{"title": "Todo A", "content": "a"}],
    )
    await session.commit()

    with patch(
        "app.agent_runtime.tools.impls.plan.update_plan.create_session",
        new=AsyncMock(return_value=session),
    ):
        tool = ToolRegistry.get_tools(names=["update_plan"], state=_make_state())[0]
        result = await tool.ainvoke(
            {
                "plan_id": plan["id"],
                "old_todos": [plan["todos"][0]],
                "new_todos": [{**plan["todos"][0], "status": "in_progress"}],
            }
        )

    payload = json.loads(result)
    assert payload["success"] is True
    assert payload["plan"]["todos"][0]["title"] == "Todo A"
    assert payload["plan"]["todos"][0]["status"] == "in_progress"
