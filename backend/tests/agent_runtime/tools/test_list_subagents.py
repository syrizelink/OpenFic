import json
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from app.agent_runtime.tools.impls.orchestration.list_subagents import (
    ListSubagentsInput,
    ListSubagentsTool,
)


@pytest.mark.asyncio
async def test_list_subagents_filters_rows_and_returns_reusable_identities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.agent_runtime.tools.impls.orchestration.list_subagents as list_module

    rows = [
        SimpleNamespace(
            dispatch_id="dispatch-completed",
            agent_key="writer",
            metadata_json={"agent_number": "#1001"},
            status="completed",
            is_active=True,
        ),
        SimpleNamespace(
            dispatch_id="dispatch-error",
            agent_key="reviewer",
            metadata_json={},
            status="error",
            is_active=True,
        ),
    ]
    db_session = object()
    list_child_runs = cast(Any, AsyncMock(return_value=rows))

    async def noop(*_args, **_kwargs) -> None:
        return None

    async def open_session(*_args, **_kwargs) -> object:
        return db_session

    monkeypatch.setattr(list_module, "ensure_primary", noop)
    monkeypatch.setattr(list_module, "open_session", open_session)
    monkeypatch.setattr(list_module, "close_session", noop)
    monkeypatch.setattr(list_module, "list_child_runs_for_parent", list_child_runs)
    tool = cast(
        Any,
        ListSubagentsTool(
            _state={
                "session_id": "parent",
                "project_id": "project-1",
                "active_agent": "primary",
            }
        ),
    )

    result = json.loads(await tool._execute(status=["completed", "error"]))

    assert result == [
        {
            "dispatch_id": "dispatch-completed",
            "agent_key": "writer",
            "agent_number": "#1001",
            "status": "completed",
        },
        {
            "dispatch_id": "dispatch-error",
            "agent_key": "reviewer",
            "agent_number": None,
            "status": "error",
        },
    ]
    list_child_runs.assert_awaited_once_with(
        db_session,
        "parent",
        is_active=True,
        statuses=["completed", "error"],
    )


def test_list_subagents_schema_describes_supported_filters() -> None:
    schema = ListSubagentsInput.model_json_schema()

    assert set(schema["properties"]) == {"status", "return_context"}
    assert "is_active" not in schema["properties"]
    assert "status" in schema["properties"]
    assert "return_context" in schema["properties"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("return_context", "expected_prompt", "expected_result"),
    [
        ("none", None, None),
        (
            "part",
            "p" * 500 + "\n\n[内容因超出 500 字符被截断]",
            "r" * 500 + "\n\n[内容因超出 500 字符被截断]",
        ),
        ("full", "p" * 501, "r" * 501),
    ],
)
async def test_list_subagents_return_context_modes(
    monkeypatch: pytest.MonkeyPatch,
    return_context: str,
    expected_prompt: str | None,
    expected_result: str | None,
) -> None:
    import app.agent_runtime.tools.impls.orchestration.list_subagents as list_module

    row = SimpleNamespace(
        id="child-1",
        dispatch_id="dispatch-1",
        agent_key="writer",
        metadata_json={"agent_number": "#1001"},
        status="completed",
        is_active=True,
    )
    latest_request = SimpleNamespace(
        content="p" * 501,
        assistant_content="r" * 501,
        status="completed",
    )
    db_session = object()
    list_child_runs = cast(Any, AsyncMock(return_value=[row]))
    get_latest_requests = cast(
        Any,
        AsyncMock(return_value={row.id: latest_request}),
    )

    async def noop(*_args, **_kwargs) -> None:
        return None

    async def open_session(*_args, **_kwargs) -> object:
        return db_session

    monkeypatch.setattr(list_module, "ensure_primary", noop)
    monkeypatch.setattr(list_module, "open_session", open_session)
    monkeypatch.setattr(list_module, "close_session", noop)
    monkeypatch.setattr(list_module, "list_child_runs_for_parent", list_child_runs)
    monkeypatch.setattr(
        list_module,
        "get_latest_child_run_requests",
        get_latest_requests,
    )
    tool = cast(
        Any,
        ListSubagentsTool(
            _state={"session_id": "parent", "project_id": "project-1"}
        ),
    )

    payload = json.loads(await tool._execute(return_context=return_context))
    subagent = payload[0]

    if expected_prompt is None:
        assert "prompt" not in subagent
        assert "result" not in subagent
        get_latest_requests.assert_not_awaited()
    else:
        assert subagent["prompt"] == expected_prompt
        assert subagent["result"] == expected_result
        get_latest_requests.assert_awaited_once_with(db_session, [row.id])


@pytest.mark.asyncio
async def test_list_subagents_omits_result_when_last_request_has_no_assistant_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.agent_runtime.tools.impls.orchestration.list_subagents as list_module

    row = SimpleNamespace(
        id="child-1",
        dispatch_id="dispatch-1",
        agent_key="writer",
        metadata_json={},
        status="running",
        is_active=True,
    )
    db_session = object()
    list_child_runs = cast(Any, AsyncMock(return_value=[row]))
    get_latest_requests = cast(
        Any,
        AsyncMock(
            return_value={
                row.id: SimpleNamespace(
                    content="current prompt",
                    assistant_content=None,
                    status="running",
                )
            }
        ),
    )

    async def noop(*_args, **_kwargs) -> None:
        return None

    async def open_session(*_args, **_kwargs) -> object:
        return db_session

    monkeypatch.setattr(list_module, "ensure_primary", noop)
    monkeypatch.setattr(list_module, "open_session", open_session)
    monkeypatch.setattr(list_module, "close_session", noop)
    monkeypatch.setattr(list_module, "list_child_runs_for_parent", list_child_runs)
    monkeypatch.setattr(
        list_module,
        "get_latest_child_run_requests",
        get_latest_requests,
    )
    tool = cast(
        Any,
        ListSubagentsTool(
            _state={"session_id": "parent", "project_id": "project-1"}
        ),
    )

    subagent = json.loads(await tool._execute(return_context="part"))[0]

    assert subagent["prompt"] == "current prompt"
    assert "result" not in subagent
