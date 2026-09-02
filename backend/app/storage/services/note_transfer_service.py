# -*- coding: utf-8 -*-
"""笔记 Markdown 导入与文件导出业务逻辑。"""

from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
import re
from typing import Literal
import zipfile

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.editor_content_limits import validate_editor_content
from app.core.errors import NotFoundError
from app.core.txt_parser import decode_text_content
from app.storage.models.note import Note, NoteCategory
from app.storage.models.project import Project
from app.storage.repos import note_category_repo, note_repo, project_repo
from app.storage.services import note_service

NoteImportFileType = Literal["md", "zip"]
MAX_NOTE_IMPORT_FILE_SIZE = 50 * 1024 * 1024
MAX_NOTE_CATEGORY_DEPTH = 2
MAX_NOTE_TITLE_LENGTH = 200


@dataclass(frozen=True)
class ParsedNote:
    """待导入的单个笔记。"""

    title: str
    content: str
    category_path: tuple[str, ...]


@dataclass(frozen=True)
class NoteImportPreview:
    """笔记导入解析结果。"""

    file_type: NoteImportFileType
    notes: tuple[ParsedNote, ...]
    ignored_file_count: int

    @property
    def category_count(self) -> int:
        category_paths = {
            parsed.category_path[:depth]
            for parsed in self.notes
            for depth in range(1, len(parsed.category_path) + 1)
        }
        return len(category_paths)


@dataclass(frozen=True)
class NoteImportResult:
    """笔记导入结果。"""

    file_type: NoteImportFileType
    imported_note_count: int
    imported_category_count: int
    ignored_file_count: int


@dataclass(frozen=True)
class ExportFile:
    """待返回给 API 层的导出文件。"""

    filename: str
    content: bytes
    media_type: str


def parse_note_import(filename: str, content: bytes) -> NoteImportPreview:
    """解析 Markdown 或 ZIP 笔记导入文件。"""
    if len(content) > MAX_NOTE_IMPORT_FILE_SIZE:
        raise ValueError("导入文件大小超过限制（最大 50MB）")

    suffix = _get_suffix(filename)
    if suffix == ".md":
        return _parse_markdown_file(filename, content)
    if suffix == ".zip":
        return _parse_zip_archive(content)
    raise ValueError("不支持的文件类型，仅支持 .md 或 .zip 文件")


async def preview_note_import(
    session: AsyncSession,
    project_id: str,
    filename: str,
    content: bytes,
) -> NoteImportPreview:
    """校验项目并解析笔记导入文件。"""
    await _get_project(session, project_id)
    return parse_note_import(filename, content)


async def import_notes(
    session: AsyncSession,
    project_id: str,
    filename: str,
    content: bytes,
) -> NoteImportResult:
    """解析并在单个事务中创建导入的分类和笔记。"""
    preview = await preview_note_import(session, project_id, filename, content)
    category_ids: dict[tuple[str, ...], str] = {}

    for parsed in preview.notes:
        parent_id: str | None = None
        for depth in range(1, len(parsed.category_path) + 1):
            category_path = parsed.category_path[:depth]
            category_id = category_ids.get(category_path)
            if category_id is None:
                category = await note_service.create_category(
                    session,
                    project_id=project_id,
                    parent_id=parent_id,
                    title=parsed.category_path[depth - 1],
                )
                category_id = category.id
                category_ids[category_path] = category_id
            parent_id = category_id

        await note_service.create_note(
            session,
            project_id=project_id,
            category_id=parent_id,
            title=parsed.title,
            content=parsed.content,
        )

    return NoteImportResult(
        file_type=preview.file_type,
        imported_note_count=len(preview.notes),
        imported_category_count=len(category_ids),
        ignored_file_count=preview.ignored_file_count,
    )


async def export_note(session: AsyncSession, note_id: str) -> ExportFile:
    """生成单个笔记的 Markdown 文件。"""
    note = await note_service.get_note(session, note_id)
    filename = f"{_safe_archive_component(note.title, '未命名笔记')}.md"
    return ExportFile(
        filename=filename,
        content=note.content.encode("utf-8"),
        media_type="text/markdown",
    )


async def export_category(session: AsyncSession, category_id: str) -> ExportFile:
    """生成包含分类目录的 ZIP 文件。"""
    category = await note_category_repo.get_by_id(session, category_id)
    if category is None:
        raise NotFoundError(f"分类不存在: {category_id}")

    categories = await note_category_repo.list_by_project(session, category.project_id)
    notes = await note_repo.list_by_project(session, category.project_id, include_hidden=True)
    children_by_parent: dict[str | None, list[NoteCategory]] = {}
    for item in categories:
        children_by_parent.setdefault(item.parent_id, []).append(item)
    notes_by_category: dict[str, list[Note]] = {}
    for note in notes:
        if note.category_id is not None:
            notes_by_category.setdefault(note.category_id, []).append(note)

    root_name = _safe_archive_component(category.title, "未命名分类")
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        _write_category_to_zip(
            archive,
            category,
            [root_name],
            children_by_parent,
            notes_by_category,
        )

    return ExportFile(
        filename=f"{root_name}.zip",
        content=output.getvalue(),
        media_type="application/zip",
    )


def _parse_markdown_file(filename: str, content: bytes) -> NoteImportPreview:
    text, _encoding = decode_text_content(content)
    basename = PurePosixPath(filename.replace("\\", "/")).name
    title = PurePosixPath(basename).stem
    _validate_title(title, "笔记")
    validate_editor_content(text)
    return NoteImportPreview(
        file_type="md",
        notes=(ParsedNote(title=title, content=text, category_path=()),),
        ignored_file_count=0,
    )


def _parse_zip_archive(content: bytes) -> NoteImportPreview:
    notes: list[ParsedNote] = []
    ignored_file_count = 0
    total_uncompressed_size = 0

    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue

                total_uncompressed_size += max(info.file_size, 0)
                if total_uncompressed_size > MAX_NOTE_IMPORT_FILE_SIZE:
                    raise ValueError("压缩包解压后的文件总大小超过限制（最大 50MB）")

                path = _normalize_archive_path(info.filename)
                if not path.lower().endswith(".md"):
                    ignored_file_count += 1
                    continue

                parts = path.split("/")
                category_path = tuple(parts[:-1])
                if len(category_path) > MAX_NOTE_CATEGORY_DEPTH:
                    raise ValueError("压缩包中的分类层级不能超过两级")
                for category_title in category_path:
                    _validate_title(category_title, "分类")

                title = PurePosixPath(parts[-1]).stem
                _validate_title(title, "笔记")
                text, _encoding = decode_text_content(archive.read(info))
                validate_editor_content(text)
                notes.append(
                    ParsedNote(
                        title=title,
                        content=text,
                        category_path=category_path,
                    )
                )
    except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, RuntimeError) as exc:
        raise ValueError("压缩包无法读取，请确认文件没有损坏或加密") from exc

    if not notes:
        raise ValueError("压缩包内未找到 Markdown 文件")

    return NoteImportPreview(
        file_type="zip",
        notes=tuple(notes),
        ignored_file_count=ignored_file_count,
    )


def _get_suffix(filename: str) -> str:
    return PurePosixPath(filename.replace("\\", "/")).suffix.lower()


def _normalize_archive_path(filename: str) -> str:
    normalized = filename.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("压缩包包含不安全的文件路径")

    parts = [part for part in path.parts if part not in {"", "."}]
    if not parts:
        raise ValueError("压缩包包含无效的文件路径")
    return "/".join(parts)


def _validate_title(title: str, label: str) -> None:
    if not title.strip():
        raise ValueError(f"{label}标题不能为空")
    if len(title) > MAX_NOTE_TITLE_LENGTH:
        raise ValueError(f"{label}标题不能超过 {MAX_NOTE_TITLE_LENGTH} 个字符")


_INVALID_ARCHIVE_COMPONENTS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def _safe_archive_component(value: str, fallback: str) -> str:
    sanitized = _INVALID_ARCHIVE_COMPONENTS.sub("_", value).strip().strip(".")
    return (sanitized or fallback)[:MAX_NOTE_TITLE_LENGTH]


def _unique_archive_component(value: str, used: set[str]) -> str:
    candidate = value
    counter = 1
    while candidate in used:
        suffix = f"({counter})"
        candidate = f"{value[: MAX_NOTE_TITLE_LENGTH - len(suffix)]}{suffix}"
        counter += 1
    used.add(candidate)
    return candidate


def _write_category_to_zip(
    archive: zipfile.ZipFile,
    category: NoteCategory,
    path: list[str],
    children_by_parent: dict[str | None, list[NoteCategory]],
    notes_by_category: dict[str, list[Note]],
) -> None:
    archive.writestr(f"{'/'.join(path)}/", b"")
    used_note_names: set[str] = set()
    for note in notes_by_category.get(category.id, []):
        note_name = _safe_archive_component(note.title, "未命名笔记")
        filename = _unique_archive_component(f"{note_name}.md", used_note_names)
        archive.writestr("/".join([*path, filename]), note.content.encode("utf-8"))

    used_category_names: set[str] = set()
    for child in children_by_parent.get(category.id, []):
        child_name = _safe_archive_component(child.title, "未命名分类")
        child_name = _unique_archive_component(child_name, used_category_names)
        _write_category_to_zip(
            archive,
            child,
            [*path, child_name],
            children_by_parent,
            notes_by_category,
        )


async def _get_project(session: AsyncSession, project_id: str) -> Project:
    project = await project_repo.get_by_id(session, project_id)
    if project is None:
        raise NotFoundError(f"项目不存在: {project_id}")
    return project
