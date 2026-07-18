import importlib
import json
import sys
from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.agent_runtime.tools.impls.plan._shared import PlanTodoInput
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
async def test_write_plan_tool_returns_success_status_after_replacing_session_todos() -> None:
    _reload_all_tool_impls()
    session = _fake_session()
    snapshot = {
        "todos": [
            {
                "content": "Review the outline",
                "status": "in_progress",
                "priority": "high",
            }
        ]
    }

    with patch(
        "app.agent_runtime.tools.impls.plan.write_plan.create_session",
        new=AsyncMock(return_value=session),
    ), patch(
        "app.agent_runtime.tools.impls.plan.write_plan.plan_service.write_plan",
        new=AsyncMock(return_value=snapshot),
    ) as write_plan_service:
        tool = ToolRegistry.get_tools(
            names=["write_plan"],
            state={
                **_make_state(),
                "parent_session_id": "parent-1",
            },
        )[0]
        result = await tool.ainvoke({"todos": snapshot["todos"]})

    payload = json.loads(result)
    assert payload == {
        "success": True,
    }
    assert write_plan_service.await_args is not None
    assert write_plan_service.await_args.kwargs["runtime_state"]["session_id"] == "session-1"
    assert write_plan_service.await_args.kwargs["todos"] == snapshot["todos"]
    session.commit.assert_awaited_once()
    session.close.assert_awaited_once()


def test_write_plan_schema_requires_complete_todo_values() -> None:
    _reload_all_tool_impls()
    tool = ToolRegistry.get_tools(names=["write_plan"], state=_make_state())[0]

    schema = tool.args_schema.model_json_schema()

    assert schema["required"] == ["todos"]
    todo_schema = schema["$defs"]["PlanTodoInput"]
    assert todo_schema["required"] == ["content", "status", "priority"]
    assert set(todo_schema["properties"]) == {"content", "status", "priority"}


def test_write_plan_todo_input_accepts_complete_values() -> None:
    todo = PlanTodoInput.model_validate(
        {
            "content": "Review the outline",
            "status": "pending",
            "priority": "medium",
        }
    )

    assert todo.content == "Review the outline"
    assert todo.status == "pending"
    assert todo.priority == "medium"


def test_write_plan_is_registered() -> None:
    _reload_all_tool_impls()

    registered_names = set(ToolRegistry.list_names())

    assert "write_plan" in registered_names
