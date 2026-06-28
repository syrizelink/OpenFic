from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.agent_runtime.agents.tool_categories import TOOL_CATEGORIES
from app.agent_runtime.tools.base import HookContext, HookResult
from app.socket.emitter import emit
from app.socket.handlers import agent_session_room

CHAPTER_WRITE_TOOL_NAMES = frozenset(TOOL_CATEGORIES["chapter_write"])


def _parse_output(output: str | None) -> dict[str, Any] | None:
    if not isinstance(output, str) or not output:
        return None
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _extract_chapter_id(result: dict[str, Any]) -> str | None:
    chapter = result.get("chapter")
    if isinstance(chapter, dict):
        chapter_id = chapter.get("id")
        if isinstance(chapter_id, str) and chapter_id:
            return chapter_id

    data = result.get("data")
    if isinstance(data, dict):
        chapter = data.get("chapter")
        if isinstance(chapter, dict):
            chapter_id = chapter.get("id")
            if isinstance(chapter_id, str) and chapter_id:
                return chapter_id
        chapter_id = data.get("chapter_id")
        if isinstance(chapter_id, str) and chapter_id:
            return chapter_id

    chapter_id = result.get("chapter_id")
    if isinstance(chapter_id, str) and chapter_id:
        return chapter_id
    return None


async def chapter_refresh_post_hook(context: HookContext) -> HookResult:
    if context.tool_name not in CHAPTER_WRITE_TOOL_NAMES:
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
    chapter_id = _extract_chapter_id(result)
    if chapter_id:
        payload["chapter_id"] = chapter_id

    await emit(
        "agent:chapter_refresh",
        payload,
        room=agent_session_room(target_session_id),
    )
    return HookResult()
