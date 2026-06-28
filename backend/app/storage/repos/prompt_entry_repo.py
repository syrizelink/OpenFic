# -*- coding: utf-8 -*-
"""
PromptEntry Repository - 提示词条目数据访问层。
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.prompt_entry import PromptEntry


async def create(session: AsyncSession, entry: PromptEntry) -> PromptEntry:
    """创建提示词条目。"""
    session.add(entry)
    await session.flush()
    await session.refresh(entry)
    return entry


async def create_many(
    session: AsyncSession, entries: list[PromptEntry]
) -> list[PromptEntry]:
    """批量创建提示词条目。"""
    session.add_all(entries)
    await session.flush()
    for entry in entries:
        await session.refresh(entry)
    return entries


async def get_by_id(session: AsyncSession, entry_id: str) -> PromptEntry | None:
    """根据ID获取提示词条目。"""
    result = await session.execute(
        select(PromptEntry).where(col(PromptEntry.id) == entry_id)
    )
    return result.scalar_one_or_none()


async def list_by_version(
    session: AsyncSession, version_id: str, enabled_only: bool = False
) -> list[PromptEntry]:
    """获取某个版本的所有提示词条目。"""
    query = select(PromptEntry).where(col(PromptEntry.version_id) == version_id)
    if enabled_only:
        query = query.where(col(PromptEntry.is_enabled))
    query = query.order_by(
        col(PromptEntry.order_index).asc(),
        col(PromptEntry.created_at).asc(),
        col(PromptEntry.id).asc(),
    )

    result = await session.execute(query)
    return list(result.scalars().all())


async def update(session: AsyncSession, entry: PromptEntry) -> PromptEntry:
    """更新提示词条目。"""
    session.add(entry)
    await session.flush()
    await session.refresh(entry)
    return entry


async def delete_by_id(session: AsyncSession, entry_id: str) -> bool:
    """删除提示词条目。"""
    entry = await get_by_id(session, entry_id)
    if entry:
        await session.delete(entry)
        await session.flush()
        return True
    return False


async def delete_by_version(session: AsyncSession, version_id: str) -> None:
    """删除某个版本的所有提示词条目。"""
    await session.execute(
        delete(PromptEntry).where(col(PromptEntry.version_id) == version_id)
    )
    await session.flush()
