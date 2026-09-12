# -*- coding: utf-8 -*-
"""WorldInfo Service - lapisan logika bisnis buku dunia."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.storage.models.world_info import WorldInfo
from app.storage.repos import project_repo, world_info_entry_repo, world_info_repo

INTERNAL_WORLD_INFO_NAME = ""


# ============== Operasi buku dunia ==============


async def get_world_info(session: AsyncSession, world_info_id: str) -> WorldInfo:
    """
    Mengambil buku dunia.

    Args:
        session: session basis data.
        world_info_id: ID buku dunia.

    Returns:
        Instance buku dunia.

    Raises:
        NotFoundError: Buku dunia tidak ditemukan.
    """
    world_info = await world_info_repo.get_by_id(session, world_info_id)
    if world_info is None:
        raise NotFoundError(f"Buku dunia tidak ditemukan: {world_info_id}")
    return world_info


async def get_or_create_world_info_by_project(
    session: AsyncSession, project_id: str
) -> WorldInfo:
    """Mengambil buku dunia tunggal proyek berdasarkan ID proyek, dibuat otomatis bila tidak ada."""
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"Proyek tidak ditemukan: {project_id}")

    world_info = await world_info_repo.get_by_project_id(session, project_id)
    if world_info is not None:
        return world_info

    return await world_info_repo.create(
        session,
        WorldInfo(
            project_id=project_id,
            name=INTERNAL_WORLD_INFO_NAME,
            description="",
        ),
    )


async def delete_world_info(session: AsyncSession, world_info_id: str) -> None:
    """
    Menghapus buku dunia beserta seluruh entrinya.

    Args:
        session: session basis data.
        world_info_id: ID buku dunia.

    Raises:
        NotFoundError: Buku dunia tidak ditemukan.
    """
    world_info = await get_world_info(session, world_info_id)

    # Hapus semua entri lebih dahulu
    await world_info_entry_repo.delete_by_world_info(session, world_info_id)

    # Baru hapus buku dunia
    await world_info_repo.delete(session, world_info)
