# -*- coding: utf-8 -*-
"""Task message repository."""

from datetime import UTC, datetime

from sqlalchemy import delete as sql_delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.task_message import TaskMessage


async def create(session: AsyncSession, message: TaskMessage) -> TaskMessage:
    session.add(message)
    await session.flush()
    await session.refresh(message)
    return message


async def create_many(
    session: AsyncSession, messages: list[TaskMessage]
) -> list[TaskMessage]:
    if not messages:
        return []
    session.add_all(messages)
    await session.flush()
    for message in messages:
        await session.refresh(message)
    return messages


async def list_by_task(session: AsyncSession, task_id: str) -> list[TaskMessage]:
    result = await session.execute(
        select(TaskMessage)
        .where(col(TaskMessage.task_id) == task_id)
        .order_by(col(TaskMessage.created_at).asc())
    )
    return list(result.scalars().all())


async def list_by_task_before_message(
    session: AsyncSession,
    task_id: str,
    message_id: str,
) -> list[TaskMessage]:
    target = await session.get(TaskMessage, message_id)
    if not target:
        return []
    result = await session.execute(
        select(TaskMessage)
        .where(col(TaskMessage.task_id) == task_id)
        .where(col(TaskMessage.created_at) < target.created_at)
        .order_by(col(TaskMessage.created_at).asc())
    )
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, message_id: str) -> TaskMessage | None:
    return await session.get(TaskMessage, message_id)


async def delete_by_task(session: AsyncSession, task_id: str) -> None:
    await session.execute(sql_delete(TaskMessage).where(col(TaskMessage.task_id) == task_id))
    await session.flush()


async def delete_after_created_at(
    session: AsyncSession,
    task_id: str,
    created_at: datetime,
) -> None:
    await session.execute(
        sql_delete(TaskMessage)
        .where(col(TaskMessage.task_id) == task_id)
        .where(col(TaskMessage.created_at) >= created_at)
    )
    await session.flush()


async def touch(session: AsyncSession, message: TaskMessage) -> TaskMessage:
    message.updated_at = datetime.now(UTC)
    session.add(message)
    await session.flush()
    await session.refresh(message)
    return message
