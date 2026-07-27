import json

import pytest

from app.agent_runtime.tools.base import HookContext


@pytest.mark.asyncio
async def test_note_refresh_hook_marks_delete_operation(monkeypatch) -> None:
    from app.agent_runtime.tools.hooks.note_refresh import note_refresh_post_hook

    captured: list[tuple[str, dict, str | None]] = []

    async def fake_emit(event: str, data: dict, *, room: str | None = None) -> None:
        captured.append((event, data, room))

    monkeypatch.setattr("app.agent_runtime.tools.hooks.note_refresh.emit", fake_emit)

    await note_refresh_post_hook(
        HookContext(
            tool_name="delete_note",
            access_level="write",
            args={},
            state={"session_id": "session-1", "project_id": "project-1"},
            output=json.dumps(
                {
                    "success": True,
                    "metadata": {"note_diff": {"note_id": "note-1"}},
                },
                ensure_ascii=False,
            ),
        )
    )

    assert captured[0][0] == "agent:note_refresh"
    assert captured[0][1]["operation"] == "delete"
    assert captured[0][1]["note_id"] == "note-1"
