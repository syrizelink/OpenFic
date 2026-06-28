from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.agent_runtime.agents.tool_categories import TOOL_CATEGORIES
from app.agent_runtime.tools.base import HookContext, HookResult
from app.socket.emitter import emit
from app.socket.handlers import agent_session_room
from loguru import logger

NOTE_WRITE_TOOL_NAMES = frozenset(TOOL_CATEGORIES["note_write"])


def _parse_output(output: str | None) -> dict[str, Any] | None:
    if not isinstance(output, str) or not output:
        return None
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _extract_note_id(result: dict[str, Any]) -> str | None:
    note = result.get("note")
    if isinstance(note, dict):
        note_id = note.get("id")
        if isinstance(note_id, str) and note_id:
            return note_id

    note_diff = result.get("note_diff")
    if isinstance(note_diff, dict):
        note_id = note_diff.get("note_id")
        if isinstance(note_id, str) and note_id:
            return note_id

    return None


async def note_refresh_post_hook(context: HookContext) -> HookResult:
    if context.tool_name not in NOTE_WRITE_TOOL_NAMES:
        return HookResult()

    result = _parse_output(context.output)
    if not result or result.get("success") is not True:
        return HookResult()

    target_session_id = context.state.get("parent_session_id") or context.state.get("session_id")
    project_id = context.state.get("project_id")
    if not isinstance(target_session_id, str) or not target_session_id:
        return HookResult()
    if not isinstance(project_id, str) or not project_id:
        return HookResult()

    payload: dict[str, Any] = {
        "session_id": target_session_id,
        "project_id": project_id,
        "created_at": datetime.now(UTC).isoformat(),
    }
    note_id = _extract_note_id(result)
    if note_id:
        payload["note_id"] = note_id

    room = agent_session_room(target_session_id)
    logger.info(
        f"[note_refresh] emit agent:note_refresh tool={context.tool_name} "
        f"room={room} note_id={note_id} parent_session={context.state.get('parent_session_id')} "
        f"session={context.state.get('session_id')}"
    )
    await emit(
        "agent:note_refresh",
        payload,
        room=room,
    )
    return HookResult()
