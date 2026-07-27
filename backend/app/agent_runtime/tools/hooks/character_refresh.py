from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.agent_runtime.agents.tool_categories import TOOL_CATEGORIES
from app.agent_runtime.tools.base import HookContext, HookResult
from app.socket.emitter import emit
from app.socket.handlers import agent_session_room

CHARACTER_WRITE_TOOL_NAMES = frozenset(TOOL_CATEGORIES["character_write"])
CHARACTER_TOOL_OPERATIONS = {
    "create_character": "create",
    "edit_character": "edit",
    "delete_character": "delete",
}


def _parse_output(output: str | None) -> dict[str, Any] | None:
    if not isinstance(output, str) or not output:
        return None
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _extract_character_id(result: dict[str, Any]) -> str | None:
    metadata = result.get("metadata")
    character_diff = (
        metadata.get("character_diff") if isinstance(metadata, dict) else None
    )
    if not isinstance(character_diff, dict):
        return None
    character_id = character_diff.get("character_id")
    return character_id if isinstance(character_id, str) and character_id else None


async def character_refresh_post_hook(context: HookContext) -> HookResult:
    if context.tool_name not in CHARACTER_WRITE_TOOL_NAMES:
        return HookResult()

    result = _parse_output(context.output)
    if not result or result.get("success") is not True:
        return HookResult()

    target_session_id = context.state.get("parent_session_id") or context.state.get(
        "session_id"
    )
    project_id = context.state.get("project_id")
    if not isinstance(target_session_id, str) or not target_session_id:
        return HookResult()
    if not isinstance(project_id, str) or not project_id:
        return HookResult()

    payload: dict[str, Any] = {
        "session_id": target_session_id,
        "project_id": project_id,
        "operation": CHARACTER_TOOL_OPERATIONS.get(context.tool_name, "update"),
        "created_at": datetime.now(UTC).isoformat(),
    }
    character_id = _extract_character_id(result)
    if character_id:
        payload["character_id"] = character_id

    await emit(
        "agent:character_refresh",
        payload,
        room=agent_session_room(target_session_id),
    )
    return HookResult()
