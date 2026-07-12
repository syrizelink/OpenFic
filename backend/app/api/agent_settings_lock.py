from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.session_activity import has_active_agent_sessions

AGENT_SETTINGS_LOCKED_DETAIL = {
    "code": "agent_settings_locked",
    "message": "Agent 会话运行中，无法修改相关设置",
}


async def require_agent_settings_unlocked(session: AsyncSession) -> None:
    if await has_active_agent_sessions(session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=AGENT_SETTINGS_LOCKED_DETAIL,
        )
