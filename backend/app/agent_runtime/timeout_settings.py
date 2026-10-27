"""Persistent timeout settings for Agent model calls."""

import math
from dataclasses import dataclass
from collections.abc import Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from app.settings import settings
from app.storage.repos import setting_repo


@dataclass(frozen=True)
class AgentTimeoutSettings:
    llm_connect_timeout: float
    llm_chunk_timeout: float
    llm_request_timeout: float


def parse_agent_timeout_settings(raw: Mapping[str, str]) -> AgentTimeoutSettings:
    values = {}
    for key in AgentTimeoutSettings.__dataclass_fields__:
        default = getattr(settings, key)
        try:
            value = float(raw[key])
            if not math.isfinite(value) or not 1 <= value <= 86400:
                value = default
        except (KeyError, TypeError, ValueError, OverflowError):
            value = default
        values[key] = value
    return AgentTimeoutSettings(**values)


async def load_agent_timeout_settings(session: AsyncSession) -> AgentTimeoutSettings:
    rows = await setting_repo.get_all(session)
    return parse_agent_timeout_settings({row.key: row.value for row in rows})
