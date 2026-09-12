# -*- coding: utf-8 -*-
"""
Import Router - API impor berkas proyek.
"""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.import_schema import (
    ImportConfirmResponse,
    ImportPreviewResponse,
    PreviewChapter,
    PreviewVolume,
)
from app.core.project_import import (
    DEFAULT_IMPORT_CHUNK_SIZE,
    MAX_IMPORT_CHUNK_SIZE,
    MAX_IMPORT_FILE_SIZE,
    ImportSplitMode,
    is_supported_import_file,
    parse_project_import,
)
from app.core.txt_parser import ParseResult
from app.storage.database import get_session
from app.storage.services import import_service

router = APIRouter(prefix="/import", tags=["import"])

SUPPORTED_FILE_DETAIL = "Hanya mendukung berkas .txt, .md, atau .zip"


def _require_supported_filename(filename: str | None) -> str:
    if not is_supported_import_file(filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=SUPPORTED_FILE_DETAIL,
        )
    return filename or ""


async def _read_import_content(file: UploadFile) -> bytes:
    content = await file.read()
    if len(content) > MAX_IMPORT_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ukuran berkas melewati batas (maksimum 50MB)",
        )
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Isi berkas kosong",
        )
    return content


def _to_preview_response(result: ParseResult) -> ImportPreviewResponse:
    preview_volumes = [
        PreviewVolume(
            title=volume.title,
            chapter_count=len(volume.chapters),
            chapters=[
                PreviewChapter(
                    title=chapter.title,
                    word_count=chapter.word_count,
                    content_preview=chapter.content[:200] if chapter.content else "",
                )
                for chapter in volume.chapters
            ],
        )
        for volume in result.volumes
    ]
    return ImportPreviewResponse(
        volumes=preview_volumes,
        total_word_count=result.total_word_count,
        chapter_count=result.chapter_count,
        detected_encoding=result.detected_encoding,
    )


def _no_chapters_detail(filename: str) -> str:
    if filename.lower().endswith(".zip"):
        return "Tidak ditemukan berkas TXT atau Markdown di dalam arsip"
    return "Gagal mengurai berkas, tidak ada bab yang dapat dikenali"


@router.post(
    "/preview",
    response_model=ImportPreviewResponse,
    summary="Pratinjau berkas impor proyek",
)
async def preview_import_file(
    file: Annotated[UploadFile, File(description="Berkas TXT, Markdown, atau ZIP")],
    split_mode: Annotated[ImportSplitMode, Form(description="Mode pemisahan")] = "auto",
    chunk_size: Annotated[
        int,
        Form(
            ge=1,
            le=MAX_IMPORT_CHUNK_SIZE,
            description="Jumlah kata per bab saat pemisahan manual",
        ),
    ] = DEFAULT_IMPORT_CHUNK_SIZE,
) -> ImportPreviewResponse:
    """
    Mengunggah berkas proyek dan mengambil pratinjau hasil penguraian.

    Args:
        file: Berkas TXT, Markdown, atau ZIP.

    Returns:
        Hasil pratinjau penguraian.

    Raises:
        HTTPException: Mengembalikan 400 bila format berkas tidak didukung atau gagal diurai.
    """
    filename = _require_supported_filename(file.filename)
    content = await _read_import_content(file)
    logger.info(f"Pratinjau berkas impor: {filename}, ukuran: {len(content)} bita")

    try:
        result = parse_project_import(
            filename,
            content,
            split_mode=split_mode,
            chunk_size=chunk_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    if not result.volumes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_no_chapters_detail(filename),
        )

    return _to_preview_response(result)


@router.post(
    "/confirm",
    response_model=ImportConfirmResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Konfirmasi impor",
)
async def confirm_import(
    file: Annotated[UploadFile, File(description="Berkas TXT, Markdown, atau ZIP")],
    title: Annotated[str, Form(description="Judul buku")],
    description: Annotated[str | None, Form(description="Sinopsis")] = None,
    cover: Annotated[UploadFile | None, File(description="Gambar sampul")] = None,
    split_mode: Annotated[ImportSplitMode, Form(description="Mode pemisahan")] = "auto",
    chunk_size: Annotated[
        int,
        Form(
            ge=1,
            le=MAX_IMPORT_CHUNK_SIZE,
            description="Jumlah kata per bab saat pemisahan manual",
        ),
    ] = DEFAULT_IMPORT_CHUNK_SIZE,
    session: AsyncSession = Depends(get_session),
) -> ImportConfirmResponse:
    """
    Konfirmasi impor, membuat proyek dan seluruh bab.

    Args:
        file: Berkas TXT, Markdown, atau ZIP.
        title: Judul buku.
        description: Sinopsis (opsional).
        cover: Gambar sampul (opsional).
        session: Session basis data.

    Returns:
        Hasil impor.

    Raises:
        HTTPException: Mengembalikan error bila impor gagal.
    """
    filename = _require_supported_filename(file.filename)
    content = await _read_import_content(file)

    # Memvalidasi judul buku
    title = title.strip()
    if not title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Judul buku tidak boleh kosong",
        )

    logger.info(f"Konfirmasi impor: {filename} -> {title}")

    # Mengurai berkas
    try:
        parse_result = parse_project_import(
            filename,
            content,
            split_mode=split_mode,
            chunk_size=chunk_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    if not parse_result.volumes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_no_chapters_detail(filename),
        )

    # Memanggil lapisan service untuk menjalankan impor
    try:
        result = await import_service.confirm_import(
            session=session,
            title=title,
            description=description,
            cover_file=cover,
            volumes=parse_result.volumes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return ImportConfirmResponse(
        project_id=result.project_id,
        title=result.title,
        chapter_count=result.chapter_count,
        total_word_count=result.total_word_count,
    )


@router.post(
    "/confirm-stream",
    summary="Konfirmasi impor (progres streaming)",
)
async def confirm_import_stream(
    file: Annotated[UploadFile, File(description="Berkas TXT, Markdown, atau ZIP")],
    title: Annotated[str, Form(description="Judul buku")],
    description: Annotated[str | None, Form(description="Sinopsis")] = None,
    cover: Annotated[UploadFile | None, File(description="Gambar sampul")] = None,
    split_mode: Annotated[ImportSplitMode, Form(description="Mode pemisahan")] = "auto",
    chunk_size: Annotated[
        int,
        Form(
            ge=1,
            le=MAX_IMPORT_CHUNK_SIZE,
            description="Jumlah kata per bab saat pemisahan manual",
        ),
    ] = DEFAULT_IMPORT_CHUNK_SIZE,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """
    Konfirmasi impor, mengembalikan progres secara streaming lewat SSE.

    Format event progres:
    - {"type": "progress", "stage": "parsing", "progress": 10}
    - {"type": "progress", "stage": "creating_project", "progress": 20}
    - {"type": "progress", "stage": "saving_chapters", "progress": 30, "current": 1, "total": 100}
    - {"type": "complete", "project_id": "xxx", "chapter_count": 100, "total_word_count": 123456}
    - {"type": "error", "message": "pesan error"}
    """

    async def generate_progress():
        try:
            filename = file.filename
            if not is_supported_import_file(filename):
                yield f"data: {json.dumps({'type': 'error', 'message': SUPPORTED_FILE_DETAIL})}\n\n"
                return

            # Progres: membaca berkas
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'reading', 'progress': 5})}\n\n"

            content = await file.read()

            if len(content) > MAX_IMPORT_FILE_SIZE:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Ukuran berkas melewati batas (maksimum 50MB)'})}\n\n"
                return

            if len(content) == 0:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Isi berkas kosong'})}\n\n"
                return

            title_clean = title.strip()
            if not title_clean:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Judul buku tidak boleh kosong'})}\n\n"
                return

            # Progres: mengurai berkas
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'parsing', 'progress': 15})}\n\n"

            parse_result = parse_project_import(
                filename or "",
                content,
                split_mode=split_mode,
                chunk_size=chunk_size,
            )

            if not parse_result.volumes:
                yield f"data: {json.dumps({'type': 'error', 'message': _no_chapters_detail(filename or '')})}\n\n"
                return

            total_chapters = parse_result.chapter_count

            # Progres: membuat proyek
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'creating_project', 'progress': 25})}\n\n"

            # Memanggil lapisan service untuk menjalankan impor
            result = await import_service.confirm_import(
                session=session,
                title=title_clean,
                description=description,
                cover_file=cover,
                volumes=parse_result.volumes,
            )

            # Progres: menyimpan bab (progres simulasi, sebenarnya sudah selesai pada penyisipan massal)
            for i in range(0, total_chapters, max(1, total_chapters // 10)):
                progress = 30 + int((i / total_chapters) * 65)
                yield f"data: {json.dumps({'type': 'progress', 'stage': 'saving_chapters', 'progress': progress, 'current': i + 1, 'total': total_chapters})}\n\n"

            # Selesai
            yield f"data: {json.dumps({'type': 'complete', 'project_id': result.project_id, 'title': result.title, 'chapter_count': result.chapter_count, 'total_word_count': result.total_word_count})}\n\n"

        except Exception as e:
            logger.exception(f"Gagal mengimpor: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate_progress(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
