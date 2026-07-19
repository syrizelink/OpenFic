import json

import pytest

from app.agent_runtime.tools.base import HookContext
from app.socket.handlers import agent_session_room


@pytest.mark.asyncio
async def test_chapter_refresh_hook_emits_parent_refresh_event(monkeypatch) -> None:
    from app.agent_runtime.tools.hooks.chapter_refresh import chapter_refresh_post_hook

    captured: list[tuple[str, dict, str | None]] = []

    async def fake_emit(event: str, data: dict, *, room: str | None = None) -> None:
        captured.append((event, data, room))

    monkeypatch.setattr("app.agent_runtime.tools.hooks.chapter_refresh.emit", fake_emit)

    await chapter_refresh_post_hook(
        HookContext(
            tool_name="write_chapter",
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
                    "metadata": {"chapter_diff": {"chapter_id": "chapter-1"}},
                },
                ensure_ascii=False,
            ),
        )
    )

    assert captured[0][0] == "agent:chapter_refresh"
    assert captured[0][1]["session_id"] == "parent-session"
    assert captured[0][1]["project_id"] == "project-1"
    assert captured[0][1]["chapter_id"] == "chapter-1"
    assert isinstance(captured[0][1]["created_at"], str)
    assert captured[0][2] == agent_session_room("parent-session")


@pytest.mark.asyncio
async def test_chapter_refresh_hook_ignores_non_mutation_or_failed_output(monkeypatch) -> None:
    from app.agent_runtime.tools.hooks.chapter_refresh import chapter_refresh_post_hook

    captured: list[tuple[str, dict, str | None]] = []

    async def fake_emit(event: str, data: dict, *, room: str | None = None) -> None:
        captured.append((event, data, room))

    monkeypatch.setattr("app.agent_runtime.tools.hooks.chapter_refresh.emit", fake_emit)

    await chapter_refresh_post_hook(
        HookContext(
            tool_name="read_chapter",
            access_level="readonly",
            args={},
            state={
                "session_id": "child-session",
                "parent_session_id": "parent-session",
                "project_id": "project-1",
            },
            output=json.dumps({"success": True, "tool_name": "read_chapter"}, ensure_ascii=False),
        )
    )
    await chapter_refresh_post_hook(
        HookContext(
            tool_name="write_chapter",
            access_level="write",
            args={},
            state={
                "session_id": "child-session",
                "parent_session_id": "parent-session",
                "project_id": "project-1",
            },
            output=json.dumps({"success": False, "tool_name": "write_chapter"}, ensure_ascii=False),
        )
    )

    assert captured == []
