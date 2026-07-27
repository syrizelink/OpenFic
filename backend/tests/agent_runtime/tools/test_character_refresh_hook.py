import json

import pytest

from app.agent_runtime.tools.base import HookContext
from app.socket.handlers import agent_session_room


@pytest.mark.asyncio
async def test_character_refresh_hook_emits_parent_refresh_event(monkeypatch) -> None:
    from app.agent_runtime.tools.hooks.character_refresh import (
        character_refresh_post_hook,
    )

    captured: list[tuple[str, dict, str | None]] = []

    async def fake_emit(event: str, data: dict, *, room: str | None = None) -> None:
        captured.append((event, data, room))

    monkeypatch.setattr(
        "app.agent_runtime.tools.hooks.character_refresh.emit", fake_emit
    )

    await character_refresh_post_hook(
        HookContext(
            tool_name="edit_character",
            access_level="write",
            args={},
            state={
                "session_id": "child-session",
                "parent_session_id": "parent-session",
                "project_id": "project-1",
            },
            output=json.dumps(
                {
                    "success": True,
                    "metadata": {"character_diff": {"character_id": "character-1"}},
                },
                ensure_ascii=False,
            ),
        )
    )

    assert captured[0][0] == "agent:character_refresh"
    assert captured[0][1]["session_id"] == "parent-session"
    assert captured[0][1]["project_id"] == "project-1"
    assert captured[0][1]["operation"] == "edit"
    assert captured[0][1]["character_id"] == "character-1"
    assert isinstance(captured[0][1]["created_at"], str)
    assert captured[0][2] == agent_session_room("parent-session")


@pytest.mark.asyncio
async def test_character_refresh_hook_ignores_non_mutation_or_failed_output(
    monkeypatch,
) -> None:
    from app.agent_runtime.tools.hooks.character_refresh import (
        character_refresh_post_hook,
    )

    captured: list[tuple[str, dict, str | None]] = []

    async def fake_emit(event: str, data: dict, *, room: str | None = None) -> None:
        captured.append((event, data, room))

    monkeypatch.setattr(
        "app.agent_runtime.tools.hooks.character_refresh.emit", fake_emit
    )

    await character_refresh_post_hook(
        HookContext(
            tool_name="read_character",
            access_level="readonly",
            args={},
            state={"session_id": "session-1", "project_id": "project-1"},
            output=json.dumps({"success": True}, ensure_ascii=False),
        )
    )
    await character_refresh_post_hook(
        HookContext(
            tool_name="create_character",
            access_level="write",
            args={},
            state={"session_id": "session-1", "project_id": "project-1"},
            output=json.dumps({"success": False}, ensure_ascii=False),
        )
    )

    assert captured == []


@pytest.mark.asyncio
async def test_character_refresh_hook_emits_direct_session_refresh_event(
    monkeypatch,
) -> None:
    from app.agent_runtime.tools.hooks.character_refresh import (
        character_refresh_post_hook,
    )

    captured: list[tuple[str, dict, str | None]] = []

    async def fake_emit(event: str, data: dict, *, room: str | None = None) -> None:
        captured.append((event, data, room))

    monkeypatch.setattr(
        "app.agent_runtime.tools.hooks.character_refresh.emit", fake_emit
    )

    await character_refresh_post_hook(
        HookContext(
            tool_name="create_character",
            access_level="write",
            args={},
            state={"session_id": "session-1", "project_id": "project-1"},
            output=json.dumps(
                {
                    "success": True,
                    "metadata": {"character_diff": {"character_id": "character-1"}},
                },
                ensure_ascii=False,
            ),
        )
    )

    assert captured[0][1]["session_id"] == "session-1"
    assert captured[0][1]["operation"] == "create"
    assert captured[0][2] == agent_session_room("session-1")


@pytest.mark.asyncio
async def test_character_refresh_hook_marks_delete_operation(monkeypatch) -> None:
    from app.agent_runtime.tools.hooks.character_refresh import (
        character_refresh_post_hook,
    )

    captured: list[tuple[str, dict, str | None]] = []

    async def fake_emit(event: str, data: dict, *, room: str | None = None) -> None:
        captured.append((event, data, room))

    monkeypatch.setattr(
        "app.agent_runtime.tools.hooks.character_refresh.emit", fake_emit
    )

    await character_refresh_post_hook(
        HookContext(
            tool_name="delete_character",
            access_level="write",
            args={},
            state={"session_id": "session-1", "project_id": "project-1"},
            output=json.dumps(
                {
                    "success": True,
                    "metadata": {"character_diff": {"character_id": "character-1"}},
                },
                ensure_ascii=False,
            ),
        )
    )

    assert captured[0][1]["operation"] == "delete"
    assert captured[0][1]["character_id"] == "character-1"
