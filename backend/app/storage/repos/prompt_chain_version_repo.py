# -*- coding: utf-8 -*-
"""
PromptChainVersion Repository - 提示词链版本数据访问层。
"""

from sqlalchemy import and_, delete as sa_delete, select
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.prompt_chain_version import PromptChainVersion


async def create(
    session: AsyncSession, version: PromptChainVersion
) -> PromptChainVersion:
    """创建版本。"""
    session.add(version)
    await session.flush()
    await session.refresh(version)
    return version


async def get_by_id(
    session: AsyncSession, version_id: str
) -> PromptChainVersion | None:
    """根据ID获取版本。"""
    result = await session.execute(
        select(PromptChainVersion).where(col(PromptChainVersion.id) == version_id)
    )
    return result.scalar_one_or_none()


async def get_by_hash(
    session: AsyncSession, version_hash: str
) -> PromptChainVersion | None:
    """根据hash获取版本。"""
    result = await session.execute(
        select(PromptChainVersion).where(
            col(PromptChainVersion.version_hash) == version_hash
        )
    )
    return result.scalar_one_or_none()


async def list_by_chain_key(
    session: AsyncSession,
    mode_name: str,
    task_name: str,
    agent_name: str | None = None,
    active_only: bool = False,
) -> list[PromptChainVersion]:
    """获取某个提示词链的所有版本。"""
    conditions = [
        col(PromptChainVersion.mode_name) == mode_name,
        col(PromptChainVersion.task_name) == task_name,
    ]
    if agent_name:
        conditions.append(col(PromptChainVersion.agent_name) == agent_name)
    else:
        conditions.append(col(PromptChainVersion.agent_name).is_(None))

    if active_only:
        conditions.append(col(PromptChainVersion.is_active).is_(True))

    query = (
        select(PromptChainVersion)
        .where(and_(*conditions))
        .order_by(col(PromptChainVersion.version_number).desc())
    )

    result = await session.execute(query)
    return list(result.scalars().all())


async def get_latest_version(
    session: AsyncSession,
    mode_name: str,
    task_name: str,
    agent_name: str | None = None,
) -> PromptChainVersion | None:
    """获取最新的活跃版本。"""
    conditions = [
        col(PromptChainVersion.mode_name) == mode_name,
        col(PromptChainVersion.task_name) == task_name,
        col(PromptChainVersion.is_active).is_(True),
    ]
    if agent_name:
        conditions.append(col(PromptChainVersion.agent_name) == agent_name)
    else:
        conditions.append(col(PromptChainVersion.agent_name).is_(None))

    result = await session.execute(
        select(PromptChainVersion)
        .where(and_(*conditions))
        .order_by(col(PromptChainVersion.version_number).desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_max_version_number(
    session: AsyncSession,
    mode_name: str,
    task_name: str,
    agent_name: str | None = None,
) -> int:
    """获取某个提示词链的最大版本号。"""
    conditions = [
        col(PromptChainVersion.mode_name) == mode_name,
        col(PromptChainVersion.task_name) == task_name,
    ]
    if agent_name:
        conditions.append(col(PromptChainVersion.agent_name) == agent_name)
    else:
        conditions.append(col(PromptChainVersion.agent_name).is_(None))

    result = await session.execute(
        select(col(PromptChainVersion.version_number))
        .where(and_(*conditions))
        .order_by(col(PromptChainVersion.version_number).desc())
        .limit(1)
    )
    max_version = result.scalar_one_or_none()
    return max_version if max_version is not None else 0


async def deactivate_versions_after(
    session: AsyncSession,
    mode_name: str,
    task_name: str,
    agent_name: str | None,
    from_version_number: int,
) -> None:
    """将某个版本号之后的所有版本标记为非活跃。"""
    conditions = [
        col(PromptChainVersion.mode_name) == mode_name,
        col(PromptChainVersion.task_name) == task_name,
        col(PromptChainVersion.version_number) > from_version_number,
    ]
    if agent_name:
        conditions.append(col(PromptChainVersion.agent_name) == agent_name)
    else:
        conditions.append(col(PromptChainVersion.agent_name).is_(None))

    await session.execute(
        sa_update(PromptChainVersion)
        .where(and_(*conditions))
        .values(is_active=False)
    )
    await session.flush()


async def update(
    session: AsyncSession, version: PromptChainVersion
) -> PromptChainVersion:
    """更新版本。"""
    session.add(version)
    await session.flush()
    await session.refresh(version)
    return version


async def delete(session: AsyncSession, version_id: str) -> bool:
    """删除版本。"""
    version = await get_by_id(session, version_id)
    if version:
        await session.delete(version)
        await session.flush()
        return True
    return False


async def delete_by_chain_key(
    session: AsyncSession,
    mode_name: str,
    task_name: str,
    agent_name: str | None = None,
) -> int:
    """
    删除某个提示词链的所有版本。

    注意：由于 prompt_entries 有外键关联，需要先删除 entries。

    Returns:
        删除的版本数量。
    """
    from app.storage.models.prompt_entry import PromptEntry

    conditions = [
        col(PromptChainVersion.mode_name) == mode_name,
        col(PromptChainVersion.task_name) == task_name,
    ]
    if agent_name:
        conditions.append(col(PromptChainVersion.agent_name) == agent_name)
    else:
        conditions.append(col(PromptChainVersion.agent_name).is_(None))

    version_ids = await session.execute(
        select(col(PromptChainVersion.id)).where(and_(*conditions))
    )
    version_id_list = [v[0] for v in version_ids.fetchall()]

    if version_id_list:
        await session.execute(
            sa_delete(PromptEntry).where(
                col(PromptEntry.version_id).in_(version_id_list)
            )
        )

        await session.execute(
            sa_delete(PromptChainVersion).where(and_(*conditions))
        )
        await session.flush()
        return len(version_id_list)

    return 0
