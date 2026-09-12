"""Storage and validation for Agent image attachments."""

from __future__ import annotations

import base64
import io
from pathlib import Path
import shutil
from typing import Any

import aiofiles
from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select
from sqlmodel import col

from app.core.ids import generate_id
from app.settings import settings

MAX_AGENT_IMAGE_ATTACHMENTS = 20
MAX_AGENT_IMAGE_BYTES = 10 * 1024 * 1024
SUPPORTED_IMAGE_MIME_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})

_IMAGE_FORMATS = {
    "JPEG": ("image/jpeg", "jpg"),
    "PNG": ("image/png", "png"),
    "WEBP": ("image/webp", "webp"),
}


def ensure_agent_attachments_dir() -> Path:
    """Memastikan direktori lampiran Agent tersedia."""
    settings.agent_attachments_dir.mkdir(parents=True, exist_ok=True)
    return settings.agent_attachments_dir


def get_agent_attachment_url(storage_name: str) -> str:
    """Mengembalikan alamat statis lampiran untuk ditampilkan aplikasi."""
    return f"/agent-attachments/{storage_name}"


def serialize_agent_attachment(attachment: Any) -> dict[str, Any]:
    """Mengembalikan deskripsi lampiran minimal yang dapat ditulis ke metadata
    pesan."""
    return {
        "id": attachment.id,
        "storage_name": attachment.storage_name,
        "file_name": attachment.file_name,
        "mime_type": attachment.mime_type,
        "size_bytes": attachment.size_bytes,
        "width": attachment.width,
        "height": attachment.height,
        "url": get_agent_attachment_url(attachment.storage_name),
    }


async def load_session_attachments(
    session: AsyncSession,
    *,
    session_id: str,
    attachment_ids: list[str],
) -> list[Any]:
    """Memuat dan memvalidasi sekumpulan lampiran gambar milik sesi yang
    ditentukan."""
    unique_ids = list(dict.fromkeys(attachment_ids))
    if len(unique_ids) != len(attachment_ids):
        raise ValueError("Lampiran gambar tidak boleh berulang")
    if len(unique_ids) > MAX_AGENT_IMAGE_ATTACHMENTS:
        raise ValueError("Satu pesan paling banyak melampirkan 20 gambar")
    if not unique_ids:
        return []

    from app.agent_runtime.persistence.model import AgentAttachment

    result = await session.execute(
        select(AgentAttachment).where(
            col(AgentAttachment.session_id) == session_id,
            col(AgentAttachment.id).in_(unique_ids),
        )
    )
    attachments_by_id = {attachment.id: attachment for attachment in result.scalars()}
    missing_ids = [attachment_id for attachment_id in unique_ids if attachment_id not in attachments_by_id]
    if missing_ids:
        raise ValueError(
            "Lampiran gambar tidak ditemukan atau tidak termasuk dalam sesi saat ini"
        )
    return [attachments_by_id[attachment_id] for attachment_id in unique_ids]


async def build_image_content_blocks(
    attachments: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Membangun blok isi gambar standar dari file di sisi server untuk dikirim
    LangChain."""
    blocks: list[dict[str, str]] = []
    root = ensure_agent_attachments_dir().resolve()
    for attachment in attachments:
        storage_name = attachment.get("storage_name")
        mime_type = attachment.get("mime_type")
        if not isinstance(storage_name, str) or not isinstance(mime_type, str):
            continue
        if mime_type not in SUPPORTED_IMAGE_MIME_TYPES:
            continue
        path = (root / storage_name).resolve()
        if root not in path.parents or not path.is_file():
            continue
        async with aiofiles.open(path, "rb") as image_file:
            content = await image_file.read()
        blocks.append(
            {
                "type": "image",
                "base64": base64.b64encode(content).decode("ascii"),
                "mime_type": mime_type,
            }
        )
    return blocks


async def copy_attachments_for_fork(
    session: AsyncSession,
    *,
    source_session_id: str,
    target_session_id: str,
    target_task_id: str,
    project_id: str,
    attachment_ids: set[str],
) -> dict[str, dict[str, Any]]:
    """Menyalin lampiran sesi sumber dan mengembalikan pemetaan dari ID lampiran
    lama ke metadata baru."""
    from app.agent_runtime.persistence.model import AgentAttachment

    if not attachment_ids:
        return {}
    result = await session.execute(
        select(AgentAttachment).where(
            col(AgentAttachment.session_id) == source_session_id,
            col(AgentAttachment.id).in_(attachment_ids),
        )
    )
    root = ensure_agent_attachments_dir()
    copied: dict[str, dict[str, Any]] = {}
    for source in result.scalars():
        source_path = root / source.storage_name
        if not source_path.is_file():
            continue
        attachment_id = generate_id()
        storage_name = f"{target_session_id}/{attachment_id}{source_path.suffix}"
        target_path = root / storage_name
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(source_path.read_bytes())
        target = AgentAttachment(
            id=attachment_id,
            session_id=target_session_id,
            task_id=target_task_id,
            project_id=project_id,
            storage_name=storage_name,
            file_name=source.file_name,
            mime_type=source.mime_type,
            size_bytes=source.size_bytes,
            width=source.width,
            height=source.height,
        )
        session.add(target)
        copied[source.id] = serialize_agent_attachment(target)
    return copied


async def delete_attachments_for_message_ids(
    session: AsyncSession,
    *,
    attachment_ids: set[str],
) -> None:
    """Menghapus catatan dan file lampiran yang tidak lagi dirujuk oleh pesan yang
    dipertahankan."""
    if not attachment_ids:
        return
    from app.agent_runtime.persistence.model import AgentAttachment

    result = await session.execute(
        select(AgentAttachment).where(col(AgentAttachment.id).in_(attachment_ids))
    )
    attachments = list(result.scalars())
    root = ensure_agent_attachments_dir()
    for attachment in attachments:
        (root / attachment.storage_name).unlink(missing_ok=True)
    await session.execute(delete(AgentAttachment).where(col(AgentAttachment.id).in_(attachment_ids)))


async def delete_attachments_for_task(
    session: AsyncSession,
    *,
    task_id: str,
) -> int:
    """Menghapus file dan catatan seluruh lampiran Agent milik sebuah tugas."""
    from app.agent_runtime.persistence.model import AgentAttachment

    result = await session.execute(
        select(AgentAttachment).where(col(AgentAttachment.task_id) == task_id)
    )
    attachments = list(result.scalars())
    root = ensure_agent_attachments_dir()
    directories: set[Path] = set()
    for attachment in attachments:
        path = root / attachment.storage_name
        path.unlink(missing_ok=True)
        directories.update(path.parents)
    await session.execute(delete(AgentAttachment).where(col(AgentAttachment.task_id) == task_id))
    _remove_empty_attachment_directories(root, directories)
    return len(attachments)


async def cleanup_orphaned_agent_attachment_files(session: AsyncSession) -> int:
    """Menghapus direktori sesi yang tidak valid lebih dulu, lalu membersihkan file
    yatim pada sesi yang masih ada."""
    from app.agent_runtime.persistence.model import (
        AgentAttachment,
        AgentChildRun,
        AgentRunMessage,
    )
    from app.storage.models.task import Task

    root = settings.agent_attachments_dir
    root.mkdir(parents=True, exist_ok=True)
    result = await session.execute(select(AgentAttachment))
    attachments = list(result.scalars())
    storage_names = {attachment.storage_name for attachment in attachments}
    message_result = await session.execute(select(AgentRunMessage))
    active_session_ids = {
        message.session_id for message in message_result.scalars()
    }
    task_result = await session.execute(select(Task))
    active_session_ids.update(
        task.agent_session_id
        for task in task_result.scalars()
        if task.agent_session_id is not None
    )
    child_run_result = await session.execute(select(AgentChildRun))
    active_session_ids.update(
        child_run.child_thread_id for child_run in child_run_result.scalars()
    )
    deleted_files = 0
    directories: set[Path] = set()

    for session_dir in root.iterdir():
        if not session_dir.is_dir() or session_dir.name in active_session_ids:
            continue
        deleted_files += sum(1 for path in session_dir.rglob("*") if path.is_file())
        shutil.rmtree(session_dir)

    file_paths = [path for path in root.rglob("*") if path.is_file()]
    for path in file_paths:
        storage_name = path.relative_to(root).as_posix()
        if storage_name in storage_names:
            continue
        path.unlink(missing_ok=True)
        deleted_files += 1
        directories.update(path.parents)

    _remove_empty_attachment_directories(root, directories)

    return deleted_files


def _remove_empty_attachment_directories(root: Path, directories: set[Path]) -> None:
    for directory in sorted(directories, key=lambda item: len(item.parts), reverse=True):
        if directory == root:
            continue
        try:
            directory.rmdir()
        except OSError:
            continue


def _image_metadata(content: bytes) -> tuple[str, str, int, int]:
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
        with Image.open(io.BytesIO(content)) as image:
            format_info = _IMAGE_FORMATS.get(image.format or "")
            if format_info is None:
                raise ValueError("Hanya gambar PNG, JPEG, atau WebP yang didukung")
            mime_type, extension = format_info
            width, height = image.size
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        if (
            isinstance(exc, ValueError)
            and str(exc) == "Hanya gambar PNG, JPEG, atau WebP yang didukung"
        ):
            raise
        raise ValueError("File yang diunggah bukan gambar yang valid") from exc

    if width < 1 or height < 1:
        raise ValueError("Dimensi gambar tidak valid")
    return mime_type, extension, width, height


async def save_agent_image_attachment(
    session: AsyncSession,
    *,
    session_id: str,
    task_id: str,
    project_id: str,
    image_file: UploadFile,
) -> Any:
    """Memvalidasi dan menyimpan satu gambar milik sebuah sesi."""
    from app.agent_runtime.persistence.model import AgentAttachment

    content = await image_file.read()
    if not content:
        raise ValueError("Gambar tidak boleh kosong")
    if len(content) > MAX_AGENT_IMAGE_BYTES:
        raise ValueError("Satu gambar tidak boleh melebihi 10 MB")

    mime_type, extension, width, height = _image_metadata(content)
    attachment_id = generate_id()
    storage_name = f"{session_id}/{attachment_id}.{extension}"
    storage_path = ensure_agent_attachments_dir() / storage_name
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(content)

    attachment = AgentAttachment(
        id=attachment_id,
        session_id=session_id,
        task_id=task_id,
        project_id=project_id,
        storage_name=storage_name,
        file_name=image_file.filename or f"image.{extension}",
        mime_type=mime_type,
        size_bytes=len(content),
        width=width,
        height=height,
    )
    try:
        session.add(attachment)
        await session.commit()
        await session.refresh(attachment)
    except Exception:
        storage_path.unlink(missing_ok=True)
        raise
    return attachment
