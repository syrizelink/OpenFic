"""Notify the parent session after an agent changes a Skill."""

import json
from datetime import UTC, datetime

from app.agent_runtime.tools.base import HookContext, HookResult
from app.socket.emitter import emit
from app.socket.handlers import agent_session_room

_SKILL_WRITE_TOOLS = frozenset(
    {
        "create_skill",
        "edit_skill",
        "create_skill_reference_doc",
        "edit_skill_reference_doc",
    }
)


async def skill_refresh_post_hook(context: HookContext) -> HookResult:
    if context.tool_name not in _SKILL_WRITE_TOOLS or not context.output:
        return HookResult()
    try:
        result = json.loads(context.output)
    except (ValueError, TypeError):
        return HookResult()
    if not isinstance(result, dict) or result.get("success") is not True:
        return HookResult()
    session_id = context.state.get("parent_session_id") or context.state.get(
        "session_id"
    )
    if not isinstance(session_id, str) or not session_id:
        return HookResult()
    skill = result.get("skill")
    skill_id = skill.get("id") if isinstance(skill, dict) else result.get("skill_id")
    await emit(
        "agent:skill_refresh",
        {
            "session_id": session_id,
            "skill_id": skill_id,
            "created_at": datetime.now(UTC).isoformat(),
        },
        room=agent_session_room(session_id),
    )
    return HookResult()
