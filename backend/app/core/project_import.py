# -*- coding: utf-8 -*-
"""Project import parsing for text files and ZIP archives."""

from collections.abc import Iterable
import io
from pathlib import PurePosixPath
import posixpath
from typing import Literal
import zipfile

from app.core.txt_parser import (
    ParseResult,
    ParsedChapter,
    ParsedVolume,
    _count_words,
    decode_text_content,
    parse_txt_content,
)
from app.retrieval.internal.indexing.chunking import RecursiveCharacterChunker

ImportSplitMode = Literal["auto", "manual"]

DEFAULT_IMPORT_CHUNK_SIZE = 800
MAX_IMPORT_CHUNK_SIZE = 100_000
MAX_IMPORT_FILE_SIZE = 50 * 1024 * 1024
SUPPORTED_IMPORT_SUFFIXES = frozenset({".txt", ".md", ".zip"})
SUPPORTED_TEXT_SUFFIXES = frozenset({".txt", ".md"})


def get_import_suffix(filename: str) -> str:
    """返回上传文件的标准化扩展名。"""
    normalized = filename.replace("\\", "/")
    return PurePosixPath(normalized).suffix.lower()


def is_supported_import_file(filename: str | None) -> bool:
    """判断文件是否为支持的项目导入格式。"""
    return bool(filename) and get_import_suffix(filename or "") in SUPPORTED_IMPORT_SUFFIXES


def validate_import_options(split_mode: str, chunk_size: int) -> None:
    """校验导入分割选项。"""
    if split_mode not in {"auto", "manual"}:
        raise ValueError("分割模式无效，仅支持 auto 或 manual")
    if not 1 <= chunk_size <= MAX_IMPORT_CHUNK_SIZE:
        raise ValueError(
            f"每章字数必须在 1 到 {MAX_IMPORT_CHUNK_SIZE} 之间"
        )


def parse_project_import(
    filename: str,
    content: bytes,
    *,
    split_mode: ImportSplitMode = "auto",
    chunk_size: int = DEFAULT_IMPORT_CHUNK_SIZE,
) -> ParseResult:
    """解析项目导入文件，返回统一的卷章节结构。"""
    validate_import_options(split_mode, chunk_size)

    suffix = get_import_suffix(filename)
    if suffix in SUPPORTED_TEXT_SUFFIXES:
        if split_mode == "manual":
            return _parse_manual_text(content, chunk_size)
        return parse_txt_content(content)
    if suffix == ".zip":
        return _parse_zip_archive(content)
    raise ValueError("不支持的文件类型，仅支持 .txt、.md 或 .zip 文件")


def _parse_manual_text(content: bytes, chunk_size: int) -> ParseResult:
    text, encoding = decode_text_content(content)
    chunks = RecursiveCharacterChunker(
        chunk_size=chunk_size,
        chunk_overlap=0,
    ).split_text(text)
    chapters = [
        ParsedChapter(
            title=f"第{index}章",
            content=chunk,
            word_count=_count_words(chunk),
        )
        for index, chunk in enumerate(chunks, start=1)
    ]
    volumes = [ParsedVolume(title="第一卷", chapters=chapters)] if chapters else []
    return ParseResult(
        volumes=volumes,
        total_word_count=sum(chapter.word_count for chapter in chapters),
        chapter_count=len(chapters),
        detected_encoding=encoding,
    )


def _parse_zip_archive(content: bytes) -> ParseResult:
    volumes_by_path: dict[str, ParsedVolume] = {}
    encodings: set[str] = set()
    total_uncompressed_size = 0

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue

                total_uncompressed_size += max(info.file_size, 0)
                if total_uncompressed_size > MAX_IMPORT_FILE_SIZE:
                    raise ValueError("压缩包解压后的文本总大小超过限制（最大 50MB）")

                path = _normalize_archive_path(info.filename)
                suffix = get_import_suffix(path)
                if suffix not in SUPPORTED_TEXT_SUFFIXES:
                    continue

                member_content = archive.read(info)
                text, encoding = decode_text_content(member_content)
                encodings.add(encoding)

                parent_path = posixpath.dirname(path)
                volume = volumes_by_path.setdefault(
                    parent_path,
                    ParsedVolume(title=parent_path or "第一卷"),
                )
                chapter_title = PurePosixPath(path).stem or "正文"
                chapter_content = text.strip()
                volume.chapters.append(
                    ParsedChapter(
                        title=chapter_title,
                        content=chapter_content,
                        word_count=_count_words(chapter_content),
                    )
                )
    except (zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError) as exc:
        raise ValueError("压缩包无法读取，请确认文件没有损坏或加密") from exc

    volumes = list(volumes_by_path.values())
    chapters = [chapter for volume in volumes for chapter in volume.chapters]
    detected_encoding = _single_or_multiple(encodings)
    return ParseResult(
        volumes=volumes,
        total_word_count=sum(chapter.word_count for chapter in chapters),
        chapter_count=len(chapters),
        detected_encoding=detected_encoding,
    )


def _normalize_archive_path(filename: str) -> str:
    normalized = filename.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("压缩包包含不安全的文件路径")

    parts = [part for part in path.parts if part not in {"", "."}]
    if not parts:
        raise ValueError("压缩包包含无效的文件路径")
    return "/".join(parts)


def _single_or_multiple(values: Iterable[str]) -> str:
    encodings = set(values)
    if not encodings:
        return "utf-8"
    if len(encodings) == 1:
        return next(iter(encodings))
    return "multiple"
