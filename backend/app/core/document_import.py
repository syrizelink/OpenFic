"""Normalize multiple imported documents into the project import structure."""

from dataclasses import dataclass, replace
from pathlib import PurePosixPath
import re
from typing import Literal, Sequence

from app.core.project_import import (
    DEFAULT_IMPORT_CHUNK_SIZE,
    ImportSplitMode,
    SUPPORTED_TEXT_SUFFIXES,
    get_import_suffix,
    parse_project_import,
)
from app.core.txt_parser import (
    VOLUME_TITLE_PATTERN,
    ParseResult,
    ParsedChapter,
    ParsedVolume,
    decode_text_content,
)

ImportStructureMode = Literal["separate_volumes", "merge_volume"]
ChapterTitleMode = Literal["preserve", "continuous_numbering"]
_CHAPTER_PREFIX_PATTERN = re.compile(
    r"^\s*第\s*(?:\d+|[〇零一二两三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟]+)\s*[章节]\s*"
)


@dataclass(frozen=True)
class ImportDocument:
    filename: str
    content: bytes


def normalize_document_import(
    documents: Sequence[ImportDocument],
    *,
    split_mode: ImportSplitMode = "auto",
    chunk_size: int = DEFAULT_IMPORT_CHUNK_SIZE,
    structure_mode: ImportStructureMode = "separate_volumes",
    merged_volume_title: str | None = None,
    chapter_title_mode: ChapterTitleMode = "preserve",
) -> ParseResult:
    """Parse documents in submission order and optionally merge their chapters."""
    if structure_mode not in {"separate_volumes", "merge_volume"}:
        raise ValueError("导入结构模式无效")
    if chapter_title_mode not in {"preserve", "continuous_numbering"}:
        raise ValueError("章节标题模式无效")

    parsed_results: list[ParseResult] = []
    for document in documents:
        result = parse_project_import(
            document.filename,
            document.content,
            split_mode=split_mode,
            chunk_size=chunk_size,
        )
        if result.chapter_count == 0:
            raise ValueError(f"文件 {document.filename} 未能识别任何章节")
        parsed_results.append(
            _rename_default_text_volume(
                document.filename,
                document.content,
                result,
                split_mode,
            )
        )

    if structure_mode == "separate_volumes":
        volumes = [
            volume for result in parsed_results for volume in result.volumes
        ]
    else:
        merged_volume_title = (merged_volume_title or "").strip()
        if not 1 <= len(merged_volume_title) <= 200:
            raise ValueError("合并卷标题必须在 1 到 200 个字符之间")
        chapters = [
            chapter
            for result in parsed_results
            for volume in result.volumes
            for chapter in volume.chapters
        ]
        if chapter_title_mode == "continuous_numbering":
            chapters = _number_chapters(chapters)
        volumes = [
            ParsedVolume(
                title=merged_volume_title or "第一卷",
                chapters=chapters,
            )
        ] if chapters else []

    chapters = [chapter for volume in volumes for chapter in volume.chapters]
    return ParseResult(
        volumes=volumes,
        total_word_count=sum(chapter.word_count for chapter in chapters),
        chapter_count=len(chapters),
        detected_encoding=_combined_encoding(parsed_results),
    )


def _rename_default_text_volume(
    filename: str,
    content: bytes,
    result: ParseResult,
    split_mode: ImportSplitMode,
) -> ParseResult:
    if (
        get_import_suffix(filename) not in SUPPORTED_TEXT_SUFFIXES
        or len(result.volumes) != 1
        or result.volumes[0].title != "第一卷"
        or (split_mode == "auto" and _has_explicit_volume_title(content))
    ):
        return result

    stem = PurePosixPath(filename.replace("\\", "/")).stem
    return ParseResult(
        volumes=[ParsedVolume(title=stem or "第一卷", chapters=result.volumes[0].chapters)],
        total_word_count=result.total_word_count,
        chapter_count=result.chapter_count,
        detected_encoding=result.detected_encoding,
    )


def _has_explicit_volume_title(content: bytes) -> bool:
    text, _encoding = decode_text_content(content)
    return bool(VOLUME_TITLE_PATTERN.search(text))


def _combined_encoding(results: Sequence[ParseResult]) -> str:
    encodings = {result.detected_encoding for result in results}
    if not encodings:
        return "utf-8"
    if len(encodings) == 1:
        return next(iter(encodings))
    return "multiple"


def _number_chapters(chapters: Sequence[ParsedChapter]) -> list[ParsedChapter]:
    numbered: list[ParsedChapter] = []
    for index, chapter in enumerate(chapters, start=1):
        title = _CHAPTER_PREFIX_PATTERN.sub("", chapter.title).strip()
        normalized_title = f"第 {index} 章"
        if title:
            normalized_title = f"{normalized_title} {title}"
        numbered.append(replace(chapter, title=normalized_title))
    return numbered
