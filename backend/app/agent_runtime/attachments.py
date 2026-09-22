"""Storage, extraction, and validation for Agent attachments."""

from __future__ import annotations

import base64
import asyncio
import io
import json
import mimetypes
from pathlib import Path
import re
import shutil
from typing import Any, Literal
import warnings

import aiofiles
from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select
from sqlmodel import col

from app.core.ids import generate_id
from app.settings import settings

MAX_AGENT_ATTACHMENTS = 20
MAX_AGENT_ATTACHMENT_BYTES = 10 * 1024 * 1024
SUPPORTED_IMAGE_MIME_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})

AttachmentKind = Literal["image", "text", "pdf", "csv", "docx", "unstructured", "html"]

_TEXT_EXTENSIONS = frozenset(
    {
        "txt",
        "md",
        "go",
        "py",
        "java",
        "sh",
        "bat",
        "ps1",
        "cmd",
        "js",
        "ts",
        "css",
        "cpp",
        "hpp",
        "h",
        "c",
        "cs",
        "sql",
        "log",
        "ini",
        "pl",
        "pm",
        "r",
        "dart",
        "dockerfile",
        "env",
        "php",
        "hs",
        "hsc",
        "lua",
        "nginxconf",
        "conf",
        "m",
        "mm",
        "plsql",
        "perl",
        "rb",
        "rs",
        "db2",
        "scala",
        "bash",
        "swift",
        "vue",
        "svelte",
        "ex",
        "exs",
        "erl",
        "tsx",
        "jsx",
        "lhs",
        "json",
        "yaml",
        "yml",
        "toml",
    }
)
_UNSTRUCTURED_EXTENSIONS = frozenset(
    {"doc", "xlsx", "xls", "pptx", "ppt", "xml", "rst", "epub", "odt", "msg"}
)
_IMAGE_EXTENSIONS = frozenset({"jpg", "jpeg", "png", "webp"})

_IMAGE_FORMATS = {
    "JPEG": ("image/jpeg", "jpg"),
    "PNG": ("image/png", "png"),
    "WEBP": ("image/webp", "webp"),
}


def _attachment_extension(file_name: str) -> str:
    name = Path(file_name).name.lower()
    return name.rsplit(".", maxsplit=1)[-1] if "." in name else name


def classify_agent_attachment(file_name: str, mime_type: str | None) -> AttachmentKind | None:
    """根据文件名优先、MIME 类型兜底判断附件解析方式。"""
    extension = _attachment_extension(file_name)
    if extension in _IMAGE_EXTENSIONS or mime_type in SUPPORTED_IMAGE_MIME_TYPES:
        return "image"
    if extension == "pdf":
        return "pdf"
    if extension == "csv":
        return "csv"
    if extension == "docx":
        return "docx"
    if extension in _UNSTRUCTURED_EXTENSIONS:
        return "unstructured"
    if extension in {"html", "htm"}:
        return "html"
    if extension in _TEXT_EXTENSIONS or (mime_type or "").lower().startswith("text/"):
        return "text"
    return None


def _normalized_mime_type(file_name: str, mime_type: str | None, kind: AttachmentKind) -> str:
    provided = (mime_type or "").strip().lower()
    if provided and provided != "application/octet-stream":
        return provided
    guessed, _ = mimetypes.guess_type(file_name)
    if guessed:
        return guessed
    if kind == "image":
        return "image/png"
    if kind == "html":
        return "text/html"
    if kind == "pdf":
        return "application/pdf"
    if kind == "csv":
        return "text/csv"
    if kind == "docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if kind == "text":
        return "text/plain"
    return "application/octet-stream"


def _storage_extension(file_name: str, kind: AttachmentKind, mime_type: str) -> str:
    if kind == "image":
        return _IMAGE_FORMATS.get(mime_type.upper(), (mime_type, "bin"))[1]
    extension = Path(file_name).suffix.lower().lstrip(".")
    return extension[:20] or kind


def _join_loaded_documents(documents: list[Any]) -> str:
    return "\n\n".join(
        document.page_content.strip()
        for document in documents
        if isinstance(getattr(document, "page_content", None), str)
        and document.page_content.strip()
    )


def _extract_attachment_content_sync(path: Path, kind: AttachmentKind) -> str | None:
    if kind == "image":
        return None
    if kind == "html":
        import trafilatura

        extracted = trafilatura.extract(
            path.read_bytes(),
            include_comments=False,
            include_tables=True,
        )
        return extracted or ""

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="`langchain-community` is being sunset.*",
            category=DeprecationWarning,
        )
        from langchain_community.document_loaders import (
            CSVLoader,
            Docx2txtLoader,
            PyPDFLoader,
            TextLoader,
            UnstructuredFileLoader,
        )

    loader: Any
    if kind == "text":
        loader = TextLoader(str(path), encoding="utf-8", autodetect_encoding=True)
    elif kind == "pdf":
        loader = PyPDFLoader(str(path))
    elif kind == "csv":
        loader = CSVLoader(str(path))
    elif kind == "docx":
        loader = Docx2txtLoader(str(path))
    else:
        loader = UnstructuredFileLoader(str(path), mode="elements")
    return _join_loaded_documents(loader.load())


def _format_attachment_processing_error(error: Exception) -> str:
    """将解析器异常转换为可展示给用户和 Agent 的错误信息。"""
    error_text = str(error).strip()
    normalized_error = error_text.lower()
    if "libreoffice" in normalized_error or "soffice" in normalized_error:
        return "附件内容提取失败：当前系统环境未安装 LibreOffice，无法解析该文件。请安装 LibreOffice 后重试。"
    missing_module = getattr(error, "name", None)
    if not isinstance(missing_module, str) or not missing_module:
        missing_module_match = re.search(r"No module named ['\"]([^'\"]+)", error_text)
        missing_module = missing_module_match.group(1) if missing_module_match else None
    if isinstance(missing_module, str) and missing_module:
        return f"附件内容提取失败：当前系统环境缺少 Python 依赖 {missing_module}。"
    if error_text:
        return f"附件内容提取失败：{error_text}"
    return "附件内容提取失败：未知解析错误。"


async def _extract_attachment_content(path: Path, kind: AttachmentKind) -> str | None:
    try:
        return await asyncio.to_thread(_extract_attachment_content_sync, path, kind)
    except Exception as exc:
        raise ValueError(_format_attachment_processing_error(exc)) from exc


def ensure_agent_attachments_dir() -> Path:
    """确保 Agent 附件目录存在。"""
    settings.agent_attachments_dir.mkdir(parents=True, exist_ok=True)
    return settings.agent_attachments_dir


def get_agent_attachment_url(storage_name: str) -> str:
    """返回供应用展示的附件静态地址。"""
    return f"/agent-attachments/{storage_name}"


def count_attachment_content_lines(content: str | None) -> int:
    """返回提取文本的行数。"""
    return len(content.splitlines()) if content else 0


def serialize_agent_attachment(attachment: Any) -> dict[str, Any]:
    """返回可写入消息元数据的最小附件描述，不包含提取后的内容。"""
    return {
        "id": attachment.id,
        "storage_name": attachment.storage_name,
        "file_name": attachment.file_name,
        "mime_type": attachment.mime_type,
        "size_bytes": attachment.size_bytes,
        "content_length": attachment.content_length,
        "line_count": attachment.line_count,
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
    """加载并验证一组属于指定会话的附件。"""
    unique_ids = list(dict.fromkeys(attachment_ids))
    if len(unique_ids) != len(attachment_ids):
        raise ValueError("附件不能重复")
    if len(unique_ids) > MAX_AGENT_ATTACHMENTS:
        raise ValueError("单条消息最多附带 20 个附件")
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
        raise ValueError("附件不存在或不属于当前会话")
    return [attachments_by_id[attachment_id] for attachment_id in unique_ids]


async def build_attachment_content_blocks(
    attachments: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """从服务端附件构建供 LangChain 发送的图片块和文本引用块。"""
    blocks: list[dict[str, str]] = []
    root = ensure_agent_attachments_dir().resolve()
    for attachment in attachments:
        storage_name = attachment.get("storage_name")
        mime_type = attachment.get("mime_type")
        file_name = attachment.get("file_name")
        attachment_id = attachment.get("id")
        error = attachment.get("error")
        if isinstance(error, str) and error:
            display_name = file_name if isinstance(file_name, str) and file_name else "附件"
            blocks.append(
                {
                    "type": "text",
                    "text": f"[附件处理失败: {display_name}] {error}",
                }
            )
            continue
        if not isinstance(mime_type, str):
            continue
        kind = classify_agent_attachment(file_name or "", mime_type)
        if kind == "image":
            if not isinstance(storage_name, str) or mime_type not in SUPPORTED_IMAGE_MIME_TYPES:
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
            continue
        if not isinstance(file_name, str) or not isinstance(attachment_id, str):
            continue
        blocks.append(
            {
                "type": "text",
                "text": f"[附件: {file_name} (id: {attachment_id})]",
            }
        )
    return blocks


async def build_image_content_blocks(
    attachments: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """兼容旧调用方，仅返回图片内容块。"""
    blocks = await build_attachment_content_blocks(attachments)
    return [block for block in blocks if block.get("type") == "image"]


async def copy_attachments_for_fork(
    session: AsyncSession,
    *,
    source_session_id: str,
    target_session_id: str,
    target_task_id: str,
    project_id: str,
    attachment_ids: set[str],
) -> dict[str, dict[str, Any]]:
    """复制源会话附件，返回旧附件 ID 到新元数据的映射。"""
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
            content=source.content,
            content_length=source.content_length,
            line_count=source.line_count,
            width=source.width,
            height=source.height,
        )
        session.add(target)
        copied[source.id] = serialize_agent_attachment(target)
    return copied


async def delete_attachments_for_task(
    session: AsyncSession,
    *,
    task_id: str,
) -> int:
    """删除任务所有 Agent 附件的文件与记录。"""
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
    """清理未被持久化消息引用的附件记录、文件和残余文件。"""
    from app.agent_runtime.persistence.model import (
        AgentAttachment,
        AgentChildRun,
        AgentRunMessage,
    )
    from app.storage.models.task import Task

    root = settings.agent_attachments_dir
    root.mkdir(parents=True, exist_ok=True)
    attachment_result = await session.execute(select(AgentAttachment))
    attachments = list(attachment_result.scalars())
    message_result = await session.execute(select(AgentRunMessage))
    messages = list(message_result.scalars())
    referenced_attachment_ids: set[str] = set()
    for message in messages:
        try:
            metadata = json.loads(message.message_metadata or "{}")
        except (TypeError, ValueError):
            continue
        if not isinstance(metadata, dict):
            continue
        message_attachments = metadata.get("attachments")
        if not isinstance(message_attachments, list):
            continue
        referenced_attachment_ids.update(
            attachment["id"]
            for attachment in message_attachments
            if isinstance(attachment, dict) and isinstance(attachment.get("id"), str)
        )

    orphaned_attachments = [
        attachment for attachment in attachments if attachment.id not in referenced_attachment_ids
    ]
    retained_attachments = [
        attachment for attachment in attachments if attachment.id in referenced_attachment_ids
    ]
    deleted_files = 0
    directories: set[Path] = set()
    for attachment in orphaned_attachments:
        path = root / attachment.storage_name
        if path.is_file():
            deleted_files += 1
        path.unlink(missing_ok=True)
        directories.update(path.parents)
    if orphaned_attachments:
        await session.execute(
            delete(AgentAttachment).where(
                col(AgentAttachment.id).in_({
                    attachment.id for attachment in orphaned_attachments
                })
            )
        )

    storage_names = {attachment.storage_name for attachment in retained_attachments}
    active_session_ids = {
        message.session_id for message in messages
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
                raise ValueError("仅支持 PNG、JPEG 或 WebP 图片")
            mime_type, extension = format_info
            width, height = image.size
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        if isinstance(exc, ValueError) and str(exc) == "仅支持 PNG、JPEG 或 WebP 图片":
            raise
        raise ValueError("上传文件不是有效图片") from exc

    if width < 1 or height < 1:
        raise ValueError("图片尺寸无效")
    return mime_type, extension, width, height


async def save_agent_attachment(
    session: AsyncSession,
    *,
    session_id: str,
    task_id: str,
    project_id: str,
    file: UploadFile,
) -> Any:
    """校验、提取并保存一份会话归属附件。"""
    from app.agent_runtime.persistence.model import AgentAttachment

    file_name = Path(file.filename or "").name
    if not file_name:
        raise ValueError("附件文件名不能为空")

    mime_type = _normalized_mime_type(file_name, file.content_type, "text")
    kind = classify_agent_attachment(file_name, file.content_type or mime_type)
    if kind is None:
        raise ValueError("不支持的附件格式")

    mime_type = _normalized_mime_type(file_name, file.content_type, kind)
    content = await file.read()
    if not content:
        raise ValueError("附件不能为空")
    if len(content) > MAX_AGENT_ATTACHMENT_BYTES:
        raise ValueError("单个附件不能超过 10 MB")

    width: int | None = None
    height: int | None = None
    if kind == "image":
        mime_type, extension, width, height = _image_metadata(content)
    else:
        extension = _storage_extension(file_name, kind, mime_type)
    attachment_id = generate_id()
    storage_name = f"{session_id}/{attachment_id}.{extension}"
    storage_path = ensure_agent_attachments_dir() / storage_name
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(content)

    try:
        extracted_content = await _extract_attachment_content(storage_path, kind)
        attachment = AgentAttachment(
            id=attachment_id,
            session_id=session_id,
            task_id=task_id,
            project_id=project_id,
            storage_name=storage_name,
            file_name=file_name[:255],
            mime_type=mime_type,
            size_bytes=len(content),
            content=extracted_content,
            content_length=len(extracted_content) if extracted_content else 0,
            line_count=count_attachment_content_lines(extracted_content),
            width=width,
            height=height,
        )
        session.add(attachment)
        await session.commit()
        await session.refresh(attachment)
    except Exception:
        storage_path.unlink(missing_ok=True)
        raise
    return attachment
