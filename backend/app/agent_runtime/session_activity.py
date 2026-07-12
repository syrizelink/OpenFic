from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.agent_runtime.persistence.model import AgentChildRun
from app.agent_runtime.runner.run_registry import get_agent_run_registry
from app.storage.models.task import Task

_ACTIVE_CHILD_RUN_STATUSES = ("queued", "running", "waiting_user")


async def has_active_agent_sessions(session: AsyncSession) -> bool:
    """Return whether any parent or child agent session can still resume work."""
    if await get_agent_run_registry().has_running_tasks():
        return True

    if await _has_running_agent_task(session):
        return True

    return await _has_active_child_run(session)


async def _has_running_agent_task(session: AsyncSession) -> bool:
    result = await session.execute(
        select(Task)
        .where(col(Task.agent_session_id).is_not(None))
        .where(col(Task.is_running).is_(True))
        .limit(1)
    )
    return result.scalar_one_or_none() is not None
async def _has_active_child_run(session: AsyncSession) -> bool:
    result = await session.execute(
        select(AgentChildRun)
        .where(col(AgentChildRun.is_active).is_(True))
        .where(col(AgentChildRun.status).in_(_ACTIVE_CHILD_RUN_STATUSES))
        .limit(1)
    )
    return result.scalar_one_or_none() is not None
