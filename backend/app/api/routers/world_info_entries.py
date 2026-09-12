# -*- coding: utf-8 -*-
"""
WorldInfo Entries Router - API CRUD entri buku dunia.
"""

import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.world_info import (
    WorldInfoEntryBatchDeleteRequest,
    WorldInfoEntryBatchDeleteResponse,
    WorldInfoEntryBatchToggleRequest,
    WorldInfoEntryBatchToggleResponse,
    WorldInfoEntryBriefListResponse,
    WorldInfoEntryBriefResponse,
    WorldInfoEntryCreate,
    WorldInfoEntryMoveRequest,
    WorldInfoEntryResponse,
    WorldInfoEntrySearchMatch,
    WorldInfoEntrySearchResponse,
    WorldInfoEntrySearchResult,
    WorldInfoImportPreviewEntry,
    WorldInfoImportPreviewResponse,
    WorldInfoEntryUpdate,
)
from app.core.errors import NotFoundError
from app.storage.database import get_session
from app.storage.services import world_info_entry_service

router = APIRouter(tags=["world-info"])

MAX_IMPORT_FILE_SIZE = 10 * 1024 * 1024


def _entry_to_response(entry) -> WorldInfoEntryResponse:
    """
    Mengonversi model WorldInfoEntry menjadi model respons.

    Args:
        entry: Instance model WorldInfoEntry.

    Returns:
        WorldInfoEntryResponse.
    """
    return WorldInfoEntryResponse(
        id=entry.id,
        world_info_id=entry.world_info_id,
        uid=entry.uid,
        name=entry.name,
        order=entry.order,
        content=entry.content,
        token_count=entry.token_count,
        is_enabled=entry.is_enabled,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


def _preview_entry_to_response(
    entry: world_info_entry_service.WorldInfoImportEntry,
) -> WorldInfoImportPreviewEntry:
    """Mengonversi entri pratinjau impor menjadi model respons."""
    return WorldInfoImportPreviewEntry(
        uid=entry.uid,
        name=entry.name,
        content_preview=entry.content[:200],
        is_enabled=entry.is_enabled,
    )


def _entry_to_brief_response(entry) -> WorldInfoEntryBriefResponse:
    """Mengonversi model WorldInfoEntry menjadi model respons ringan (tanpa content)."""
    return WorldInfoEntryBriefResponse(
        id=entry.id,
        world_info_id=entry.world_info_id,
        uid=entry.uid,
        name=entry.name,
        order=entry.order,
        token_count=entry.token_count,
        is_enabled=entry.is_enabled,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


# ============== Endpoint entri buku dunia ==============


@router.post(
    "/world-info/import/preview",
    response_model=WorldInfoImportPreviewResponse,
    summary="Pratinjau impor buku dunia",
)
async def preview_world_info_import(
    file: Annotated[UploadFile, File(description="Berkas JSON buku dunia SillyTavern")],
) -> WorldInfoImportPreviewResponse:
    """Pratinjau hasil impor buku dunia SillyTavern."""
    if not file.filename or not file.filename.lower().endswith(".json"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hanya mendukung berkas .json",
        )

    content = await file.read()
    if len(content) > MAX_IMPORT_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ukuran berkas melewati batas (maksimum 10MB)",
        )
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Isi berkas kosong",
        )

    try:
        preview = world_info_entry_service.parse_sillytavern_worldbook(content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return WorldInfoImportPreviewResponse(
        entry_count=len(preview.entries),
        enabled_count=sum(1 for entry in preview.entries if entry.is_enabled),
        entries=[_preview_entry_to_response(entry) for entry in preview.entries],
    )


@router.post(
    "/world-info/{world_info_id}/entries/import-stream",
    response_model=None,
    summary="Impor entri buku dunia secara streaming",
)
async def import_entries_stream(
    world_info_id: str,
    file: Annotated[UploadFile, File(description="Berkas JSON buku dunia SillyTavern")],
    session: Annotated[AsyncSession, Depends(get_session)],
    mode: Annotated[
        Literal["append", "overwrite"],
        Query(description="Mode impor"),
    ] = "append",
) -> StreamingResponse:
    """Mengimpor entri buku dunia secara streaming dan mengembalikan progres real-time."""

    async def generate_progress():
        try:
            if not file.filename or not file.filename.lower().endswith(".json"):
                yield f"data: {json.dumps({'type': 'error', 'message': 'Hanya mendukung berkas .json'}, ensure_ascii=False)}\n\n"
                return

            yield f"data: {json.dumps({'type': 'progress', 'stage': 'reading', 'progress': 5}, ensure_ascii=False)}\n\n"
            content = await file.read()

            if len(content) > MAX_IMPORT_FILE_SIZE:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Ukuran berkas melewati batas (maksimum 10MB)'}, ensure_ascii=False)}\n\n"
                return
            if len(content) == 0:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Isi berkas kosong'}, ensure_ascii=False)}\n\n"
                return

            yield f"data: {json.dumps({'type': 'progress', 'stage': 'parsing', 'progress': 20}, ensure_ascii=False)}\n\n"
            preview = world_info_entry_service.parse_sillytavern_worldbook(content)
            total_entries = len(preview.entries)

            for index in range(total_entries):
                progress = 35 + int(((index + 1) / total_entries) * 60)
                yield f"data: {json.dumps({'type': 'progress', 'stage': 'importing_entries', 'progress': progress, 'current': index + 1, 'total': total_entries}, ensure_ascii=False)}\n\n"

            result = await world_info_entry_service.import_entries(
                session=session,
                world_info_id=world_info_id,
                entries=preview.entries,
                mode=mode,
            )

            complete_event = {
                "type": "complete",
                "world_info_id": result.world_info_id,
                "imported_count": result.imported_count,
            }
            yield f"data: {json.dumps(complete_event, ensure_ascii=False)}\n\n"
        except NotFoundError as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"
        except ValueError as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.exception(f"Gagal mengimpor buku dunia: {exc}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate_progress(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/world-info/{world_info_id}/entries",
    response_model=WorldInfoEntryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Membuat entri",
)
async def create_entry(
    world_info_id: str,
    data: WorldInfoEntryCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorldInfoEntryResponse:
    """
    Membuat entri buku dunia.

    Args:
        world_info_id: ID buku dunia.
        data: Data permintaan pembuatan.
        session: Session basis data.

    Returns:
        Entri yang dibuat.

    Raises:
        HTTPException: Buku dunia tidak ditemukan.
    """
    try:
        logger.info(f"Membuat entri: world_info_id={world_info_id}, name={data.name}")
        entry = await world_info_entry_service.create_entry(
            session,
            world_info_id,
            name=data.name,
            content=data.content,
            token_count=data.token_count,
            is_enabled=data.is_enabled,
        )
        return _entry_to_response(entry)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/world-info/{world_info_id}/entries",
    response_model=WorldInfoEntryBriefListResponse,
    summary="Mengambil daftar entri",
)
async def list_entries(
    world_info_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorldInfoEntryBriefListResponse:
    """
    Mengambil daftar entri buku dunia (ringan, tanpa content).

    Args:
        world_info_id: ID buku dunia.
        session: Session basis data.
    Returns:
        Daftar entri ringan.

    Raises:
        HTTPException: Buku dunia tidak ditemukan.
    """
    try:
        entries = await world_info_entry_service.list_entries(session, world_info_id)
        return WorldInfoEntryBriefListResponse(
            items=[_entry_to_brief_response(entry) for entry in entries],
            total=len(entries),
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/world-info-entries/{entry_id}",
    response_model=WorldInfoEntryResponse,
    summary="Mengambil detail entri",
)
async def get_entry(
    entry_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorldInfoEntryResponse:
    """
    Mengambil detail satu entri.

    Args:
        entry_id: ID entri.
        session: Session basis data.

    Returns:
        Detail entri.

    Raises:
        HTTPException: Entri tidak ditemukan.
    """
    try:
        entry = await world_info_entry_service.get_entry(session, entry_id)
        return _entry_to_response(entry)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch(
    "/world-info-entries/{entry_id}",
    response_model=WorldInfoEntryResponse,
    summary="Memperbarui entri",
)
async def update_entry(
    entry_id: str,
    data: WorldInfoEntryUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorldInfoEntryResponse:
    """
    Memperbarui entri buku dunia.

    Args:
        entry_id: ID entri.
        data: Data permintaan pembaruan.
        session: Session basis data.

    Returns:
        Entri setelah diperbarui.

    Raises:
        HTTPException: Entri tidak ditemukan.
    """
    try:
        logger.info(f"Memperbarui entri: {entry_id}")
        entry = await world_info_entry_service.update_entry(
            session,
            entry_id,
            name=data.name,
            content=data.content,
            token_count=data.token_count,
            is_enabled=data.is_enabled,
        )
        return _entry_to_response(entry)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except world_info_entry_service.WorldInfoEntryNameConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/world-info/{world_info_id}/entries",
    status_code=status.HTTP_200_OK,
    summary="Menghapus semua entri buku dunia",
)
async def delete_all_entries(
    world_info_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, int]:
    """
    Menghapus semua entri buku dunia.

    Args:
        world_info_id: ID buku dunia.
        session: Session basis data.

    Returns:
        Jumlah entri yang dihapus.
    """
    try:
        logger.info(f"Menghapus semua entri buku dunia: world_info_id={world_info_id}")
        deleted_count = await world_info_entry_service.delete_all_entries(
            session, world_info_id
        )
        return {"deleted_count": deleted_count}
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete(
    "/world-info-entries/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Menghapus entri",
)
async def delete_entry(
    entry_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """
    Menghapus entri buku dunia.

    Args:
        entry_id: ID entri.
        session: Session basis data.

    Raises:
        HTTPException: Entri tidak ditemukan.
    """
    try:
        logger.info(f"Menghapus entri: {entry_id}")
        await world_info_entry_service.delete_entry(session, entry_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/world-info-entries/{entry_id}/move",
    response_model=WorldInfoEntryBriefResponse,
    summary="Memindahkan entri",
)
async def move_entry(
    entry_id: str,
    data: WorldInfoEntryMoveRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorldInfoEntryBriefResponse:
    """
    Memindahkan entri buku dunia ke posisi baru.

    Args:
        entry_id: ID entri.
        data: Data permintaan pemindahan.
        session: Session basis data.

    Returns:
        Entri setelah dipindahkan.

    Raises:
        HTTPException: Entri tidak ditemukan atau posisi tidak valid.
    """
    try:
        logger.info(f"Memindahkan entri: {entry_id} -> order={data.new_order}")
        entry = await world_info_entry_service.move_entry(
            session, entry_id, data.new_order
        )
        return _entry_to_brief_response(entry)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/world-info-entries/{entry_id}/toggle",
    response_model=WorldInfoEntryResponse,
    summary="Mengalihkan sakelar entri",
)
async def toggle_entry(
    entry_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorldInfoEntryResponse:
    """
    Mengalihkan status sakelar entri buku dunia.

    Args:
        entry_id: ID entri.
        session: Session basis data.

    Returns:
        Entri setelah dialihkan.

    Raises:
        HTTPException: Entri tidak ditemukan.
    """
    try:
        logger.info(f"Mengalihkan sakelar entri: {entry_id}")
        entry = await world_info_entry_service.toggle_entry(session, entry_id)
        return _entry_to_response(entry)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/world-info/{world_info_id}/entries/batch/toggle",
    response_model=WorldInfoEntryBatchToggleResponse,
    summary="Mengalihkan sakelar entri secara massal",
)
async def batch_toggle_entries(
    world_info_id: str,
    data: WorldInfoEntryBatchToggleRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorldInfoEntryBatchToggleResponse:
    """Mengalihkan status sakelar entri buku dunia secara massal."""
    try:
        logger.info(f"Mengalihkan sakelar entri secara massal: world_info_id={world_info_id}, count={len(data.entry_ids)}")
        updated_count = await world_info_entry_service.batch_toggle_entries(
            session, world_info_id, data.entry_ids, data.is_enabled
        )
        return WorldInfoEntryBatchToggleResponse(updated_count=updated_count)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/world-info/{world_info_id}/entries/batch/delete",
    response_model=WorldInfoEntryBatchDeleteResponse,
    summary="Menghapus entri secara massal",
)
async def batch_delete_entries(
    world_info_id: str,
    data: WorldInfoEntryBatchDeleteRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorldInfoEntryBatchDeleteResponse:
    """Menghapus entri buku dunia secara massal."""
    try:
        logger.info(f"Menghapus entri secara massal: world_info_id={world_info_id}, count={len(data.entry_ids)}")
        deleted_count = await world_info_entry_service.batch_delete_entries(
            session, world_info_id, data.entry_ids
        )
        return WorldInfoEntryBatchDeleteResponse(deleted_count=deleted_count)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/world-info/{world_info_id}/entries/search",
    response_model=WorldInfoEntrySearchResponse,
    summary="Mencari isi entri",
)
async def search_entries(
    world_info_id: str,
    q: Annotated[str, Query(min_length=1, description="Kata kunci pencarian")],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorldInfoEntrySearchResponse:
    try:
        result = await world_info_entry_service.search_entries(
            session, world_info_id, q
        )
        return WorldInfoEntrySearchResponse(
            results=[
                WorldInfoEntrySearchResult(
                    entry_id=r.entry_id,
                    entry_name=r.entry_name,
                    uid=r.uid,
                    matches=[
                        WorldInfoEntrySearchMatch(
                            line_number=m.line_number,
                            line_text=m.line_text,
                        )
                        for m in r.matches
                    ],
                )
                for r in result.results
            ],
            total_entries=result.total_entries,
            total_matches=result.total_matches,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
