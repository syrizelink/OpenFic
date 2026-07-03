from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.agent_runtime.agents.tool_categories import TOOL_CATEGORIES
from app.agent_runtime.tools.base import HookContext, HookResult
from app.socket.emitter import emit
from app.socket.handlers import agent_session_room

WORLD_ENTRY_WRITE_TOOL_NAMES = frozenset(TOOL_CATEGORIES["world_write"])
WORLD_ENTRY_TOOL_OPERATIONS = {
    "create_world_entry": "create",
    "edit_world_entry": "edit",
    "delete_world_entry": "delete",
}


def _parse_output(output: str | None) -> dict[str, Any] | None:
    if not isinstance(output, str) or not output:
        return None
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _extract_entry_id(result: dict[str, Any]) -> str | None:
    world_entry = result.get("world_entry")
    if isinstance(world_entry, dict):
        entry_id = world_entry.get("id")
        if isinstance(entry_id, str) and entry_id:
            return entry_id

    world_entry_diff = result.get("world_entry_diff")
    if isinstance(world_entry_diff, dict):
        entry_id = world_entry_diff.get("entry_id")
        if isinstance(entry_id, str) and entry_id:
            return entry_id

    entry_id = result.get("entry_id")
    if isinstance(entry_id, str) and entry_id:
        return entry_id
    return None


def _extract_world_info_id(result: dict[str, Any], state: dict[str, Any]) -> str | None:
    world_info_id = result.get("world_info_id")
    if isinstance(world_info_id, str) and world_info_id:
        return world_info_id

    state_world_info_id = state.get("world_info_id")
    if isinstance(state_world_info_id, str) and state_world_info_id:
        return state_world_info_id
    return None


async def world_entry_refresh_post_hook(context: HookContext) -> HookResult:
    if context.tool_name not in WORLD_ENTRY_WRITE_TOOL_NAMES:
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
        "operation": WORLD_ENTRY_TOOL_OPERATIONS.get(context.tool_name, "update"),
        "created_at": datetime.now(UTC).isoformat(),
    }
    world_info_id = _extract_world_info_id(result, context.state)
    if world_info_id:
        payload["world_info_id"] = world_info_id
    entry_id = _extract_entry_id(result)
    if entry_id:
        payload["entry_id"] = entry_id

    await emit(
        "agent:world_entry_refresh",
        payload,
        room=agent_session_room(target_session_id),
    )
    return HookResult()
