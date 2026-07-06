# -*- coding: utf-8 -*-
"""
ModelProvider Repository - 模型服务提供商数据访问层。
"""

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.models.entities.model_provider import ModelProvider


async def get_all(session: AsyncSession) -> list[ModelProvider]:
    """
    获取所有提供商。

    Args:
        session: 数据库 session。

    Returns:
        提供商列表。
    """
    result = await session.execute(select(ModelProvider))
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, provider_id: str) -> ModelProvider | None:
    """
    根据 ID 获取提供商。

    Args:
        session: 数据库 session。
        provider_id: 提供商 ID。

    Returns:
        提供商实例，如果不存在则返回 None。
    """
    result = await session.execute(
        select(ModelProvider).where(col(ModelProvider.id) == provider_id)
    )
    return result.scalar_one_or_none()


async def create(
    session: AsyncSession,
    name: str,
    url: str,
    api_key_encrypted: str,
    provider_type: str,
    icon_path: str | None = None,
) -> ModelProvider:
    """
    创建提供商。

    Args:
        session: 数据库 session。
        name: 提供商名称/备注。
        url: 服务 URL。
        api_key_encrypted: 加密后的 API Key。
        provider_type: 提供商类型。
        icon_path: 图标文件路径。

    Returns:
        创建的提供商实例。
    """
    provider = ModelProvider(
        name=name,
        url=url,
        api_key_encrypted=api_key_encrypted,
        provider_type=provider_type,
        icon_path=icon_path,
    )
    session.add(provider)
    await session.flush()
    await session.refresh(provider)
    return provider


async def update(
    session: AsyncSession,
    provider_id: str,
    name: str | None = None,
    url: str | None = None,
    api_key_encrypted: str | None = None,
    provider_type: str | None = None,
    icon_path: str | None = None,
) -> ModelProvider | None:
    """
    更新提供商。

    Args:
        session: 数据库 session。
        provider_id: 提供商 ID。
        name: 提供商名称/备注。
        url: 服务 URL。
        api_key_encrypted: 加密后的 API Key。
        provider_type: 提供商类型。
        icon_path: 图标文件路径。

    Returns:
        更新后的提供商实例，如果不存在则返回 None。
    """
    provider = await get_by_id(session, provider_id)
    if not provider:
        return None

    if name is not None:
        provider.name = name
    if url is not None:
        provider.url = url
    if api_key_encrypted is not None:
        provider.api_key_encrypted = api_key_encrypted
    if provider_type is not None:
        provider.provider_type = provider_type
    if icon_path is not None:
        provider.icon_path = icon_path

    provider.updated_at = datetime.now(UTC)
    session.add(provider)
    await session.flush()
    await session.refresh(provider)
    return provider


async def delete_by_id(session: AsyncSession, provider_id: str) -> bool:
    """
    删除提供商。

    Args:
        session: 数据库 session。
        provider_id: 提供商 ID。

    Returns:
        是否成功删除。
    """
    result = await session.execute(
        delete(ModelProvider).where(col(ModelProvider.id) == provider_id)
    )
    return cast("CursorResult[Any]", result).rowcount > 0
