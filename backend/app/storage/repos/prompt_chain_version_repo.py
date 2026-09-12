# -*- coding: utf-8 -*-
"""
PromptChainVersion Repository - lapisan akses data versi rantai prompt.
"""

from sqlalchemy import and_, delete as sa_delete, select
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.storage.models.prompt_chain_version import PromptChainVersion


async def create(
    session: AsyncSession, version: PromptChainVersion
) -> PromptChainVersion:
    """Membuat versi."""
    session.add(version)
    await session.flush()
    await session.refresh(version)
    return version


async def get_by_id(
    session: AsyncSession, version_id: str
) -> PromptChainVersion | None:
    """Mengambil versi berdasarkan ID."""
    result = await session.execute(
        select(PromptChainVersion).where(col(PromptChainVersion.id) == version_id)
    )
    return result.scalar_one_or_none()


async def get_by_hash(
    session: AsyncSession, version_hash: str
) -> PromptChainVersion | None:
    """Mengambil versi berdasarkan hash."""
    result = await session.execute(
        select(PromptChainVersion).where(
            col(PromptChainVersion.version_hash) == version_hash
        )
    )
    return result.scalar_one_or_none()


async def list_by_chain_key(
    session: AsyncSession,
    prompt_id: str,
    active_only: bool = False,
) -> list[PromptChainVersion]:
    """Mengambil semua versi dari sebuah rantai prompt."""
    conditions = [col(PromptChainVersion.prompt_id) == prompt_id]

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
    prompt_id: str,
) -> PromptChainVersion | None:
    """Mengambil versi aktif terbaru."""
    conditions = [
        col(PromptChainVersion.prompt_id) == prompt_id,
        col(PromptChainVersion.is_active).is_(True),
    ]

    result = await session.execute(
        select(PromptChainVersion)
        .where(and_(*conditions))
        .order_by(col(PromptChainVersion.version_number).desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_max_version_number(
    session: AsyncSession,
    prompt_id: str,
) -> int:
    """Mengambil nomor versi terbesar dari sebuah rantai prompt."""
    conditions = [col(PromptChainVersion.prompt_id) == prompt_id]

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
    prompt_id: str,
    from_version_number: int,
) -> None:
    """Menandai semua versi setelah nomor versi tertentu sebagai tidak aktif."""
    conditions = [
        col(PromptChainVersion.prompt_id) == prompt_id,
        col(PromptChainVersion.version_number) > from_version_number,
    ]

    await session.execute(
        sa_update(PromptChainVersion)
        .where(and_(*conditions))
        .values(is_active=False)
    )
    await session.flush()


async def update(
    session: AsyncSession, version: PromptChainVersion
) -> PromptChainVersion:
    """Memperbarui versi."""
    session.add(version)
    await session.flush()
    await session.refresh(version)
    return version


async def delete(session: AsyncSession, version_id: str) -> bool:
    """Menghapus versi."""
    version = await get_by_id(session, version_id)
    if version:
        await session.delete(version)
        await session.flush()
        return True
    return False


async def delete_by_chain_key(
    session: AsyncSession,
    prompt_id: str,
) -> int:
    """
    Menghapus semua versi dari sebuah rantai prompt.

    Catatan: karena prompt_entries punya relasi foreign key, entries harus dihapus lebih dahulu.

    Returns:
        Jumlah versi yang dihapus.
    """
    from app.storage.models.prompt_entry import PromptEntry

    conditions = [col(PromptChainVersion.prompt_id) == prompt_id]

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
