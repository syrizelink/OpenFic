# -*- coding: utf-8 -*-
"""
ModelProvider Repository - lapisan akses data penyedia layanan model.
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
    Mengambil semua penyedia.

    Args:
        session: session basis data.

    Returns:
        Daftar penyedia.
    """
    result = await session.execute(select(ModelProvider))
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, provider_id: str) -> ModelProvider | None:
    """
    Mengambil penyedia berdasarkan ID.

    Args:
        session: session basis data.
        provider_id: ID penyedia.

    Returns:
        Instance penyedia, atau None jika tidak ditemukan.
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
    custom_headers_encrypted: str = "",
) -> ModelProvider:
    """
    Membuat penyedia.

    Args:
        session: session basis data.
        name: nama/catatan penyedia.
        url: URL layanan.
        api_key_encrypted: API Key setelah dienkripsi.
        custom_headers_encrypted: header permintaan kustom setelah dienkripsi.
        provider_type: jenis penyedia.
    Returns:
        Instance penyedia yang dibuat.
    """
    provider = ModelProvider(
        name=name,
        url=url,
        api_key_encrypted=api_key_encrypted,
        custom_headers_encrypted=custom_headers_encrypted,
        provider_type=provider_type,
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
    custom_headers_encrypted: str | None = None,
    provider_type: str | None = None,
) -> ModelProvider | None:
    """
    Memperbarui penyedia.

    Args:
        session: session basis data.
        provider_id: ID penyedia.
        name: nama/catatan penyedia.
        url: URL layanan.
        api_key_encrypted: API Key setelah dienkripsi.
        custom_headers_encrypted: header permintaan kustom setelah dienkripsi.
        provider_type: jenis penyedia.
    Returns:
        Instance penyedia setelah diperbarui, atau None jika tidak ditemukan.
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
    if custom_headers_encrypted is not None:
        provider.custom_headers_encrypted = custom_headers_encrypted
    if provider_type is not None:
        provider.provider_type = provider_type
    provider.updated_at = datetime.now(UTC)
    session.add(provider)
    await session.flush()
    await session.refresh(provider)
    return provider


async def delete_by_id(session: AsyncSession, provider_id: str) -> bool:
    """
    Menghapus penyedia.

    Args:
        session: session basis data.
        provider_id: ID penyedia.

    Returns:
        Apakah penghapusan berhasil.
    """
    result = await session.execute(
        delete(ModelProvider).where(col(ModelProvider.id) == provider_id)
    )
    return cast("CursorResult[Any]", result).rowcount > 0
