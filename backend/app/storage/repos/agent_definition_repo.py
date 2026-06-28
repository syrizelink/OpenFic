# -*- coding: utf-8 -*-
"""
AgentDefinition Repository - Data access for agent_definitions table.
"""

from sqlalchemy import delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.agent_runtime.persistence.model import AgentDefinitionRecord


async def get_by_key(
    session: AsyncSession, key: str
) -> AgentDefinitionRecord | None:
    result = await session.execute(
        select(AgentDefinitionRecord).where(col(AgentDefinitionRecord.key) == key)
    )
    return result.scalar_one_or_none()


async def list_all(session: AsyncSession) -> list[AgentDefinitionRecord]:
    result = await session.execute(
        select(AgentDefinitionRecord).order_by(col(AgentDefinitionRecord.order_index))
    )
    return list(result.scalars().all())


async def create(
    session: AsyncSession, record: AgentDefinitionRecord
) -> AgentDefinitionRecord:
    session.add(record)
    await session.flush()
    await session.refresh(record)
    return record


async def update(
    session: AsyncSession, record: AgentDefinitionRecord
) -> AgentDefinitionRecord:
    session.add(record)
    await session.flush()
    await session.refresh(record)
    return record


async def delete_by_key(session: AsyncSession, key: str) -> None:
    await session.execute(
        sa_delete(AgentDefinitionRecord).where(col(AgentDefinitionRecord.key) == key)
    )
    await session.flush()
