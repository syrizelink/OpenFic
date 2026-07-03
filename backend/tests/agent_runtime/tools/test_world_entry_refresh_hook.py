import json

import pytest

from app.agent_runtime.tools.base import HookContext
from app.socket.handlers import agent_session_room


@pytest.mark.asyncio
async def test_world_entry_refresh_hook_emits_parent_refresh_event(monkeypatch) -> None:
    from app.agent_runtime.tools.hooks.world_entry_refresh import world_entry_refresh_post_hook

    captured: list[tuple[str, dict, str | None]] = []

    async def fake_emit(event: str, data: dict, *, room: str | None = None) -> None:
        captured.append((event, data, room))

    monkeypatch.setattr("app.agent_runtime.tools.hooks.world_entry_refresh.emit", fake_emit)

    await world_entry_refresh_post_hook(
        HookContext(
            tool_name="edit_world_entry",
            access_level="write",
            args={},
            state={
                "session_id": "child-session",
                "parent_session_id": "parent-session",
                "project_id": "project-1",
                "world_info_id": "world-1",
            },
            output=json.dumps(
                {
                    "success": True,
                    "tool_name": "edit_world_entry",
                    "world_entry": {"id": "entry-1"},
                },
                ensure_ascii=False,
            ),
        )
    )

    assert captured[0][0] == "agent:world_entry_refresh"
    assert captured[0][1]["session_id"] == "parent-session"
    assert captured[0][1]["project_id"] == "project-1"
    assert captured[0][1]["operation"] == "edit"
    assert captured[0][1]["world_info_id"] == "world-1"
    assert captured[0][1]["entry_id"] == "entry-1"
    assert isinstance(captured[0][1]["created_at"], str)
    assert captured[0][2] == agent_session_room("parent-session")


@pytest.mark.asyncio
async def test_world_entry_refresh_hook_ignores_non_mutation_or_failed_output(monkeypatch) -> None:
    from app.agent_runtime.tools.hooks.world_entry_refresh import world_entry_refresh_post_hook

    captured: list[tuple[str, dict, str | None]] = []

    async def fake_emit(event: str, data: dict, *, room: str | None = None) -> None:
        captured.append((event, data, room))

    monkeypatch.setattr("app.agent_runtime.tools.hooks.world_entry_refresh.emit", fake_emit)

    await world_entry_refresh_post_hook(
        HookContext(
            tool_name="read_world_entry",
            access_level="readonly",
            args={},
            state={"session_id": "session-1", "project_id": "project-1"},
            output=json.dumps({"success": True}, ensure_ascii=False),
        )
    )
    await world_entry_refresh_post_hook(
        HookContext(
            tool_name="create_world_entry",
            access_level="write",
            args={},
            state={"session_id": "session-1", "project_id": "project-1"},
            output=json.dumps({"success": False}, ensure_ascii=False),
        )
    )

    assert captured == []


@pytest.mark.asyncio
async def test_world_entry_refresh_hook_marks_delete_operation(monkeypatch) -> None:
    from app.agent_runtime.tools.hooks.world_entry_refresh import world_entry_refresh_post_hook

    captured: list[tuple[str, dict, str | None]] = []

    async def fake_emit(event: str, data: dict, *, room: str | None = None) -> None:
        captured.append((event, data, room))

    monkeypatch.setattr("app.agent_runtime.tools.hooks.world_entry_refresh.emit", fake_emit)

    await world_entry_refresh_post_hook(
        HookContext(
            tool_name="delete_world_entry",
            access_level="write",
            args={},
            state={"session_id": "session-1", "project_id": "project-1"},
            output=json.dumps(
                {
                    "success": True,
                    "tool_name": "delete_world_entry",
                    "world_info_id": "world-1",
                    "entry_id": "entry-1",
                },
                ensure_ascii=False,
            ),
        )
    )

    assert captured[0][1]["operation"] == "delete"
    assert captured[0][1]["world_info_id"] == "world-1"
    assert captured[0][1]["entry_id"] == "entry-1"
