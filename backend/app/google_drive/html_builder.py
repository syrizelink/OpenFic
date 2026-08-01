# -*- coding: utf-8 -*-
"""
整本书 HTML 组装。

书名为 H1、卷为 H2、章节为 H3，正文每段 <p>。Google 导入后标题会保留为
Heading 样式，文档大纲可直接跳转。
"""

from __future__ import annotations

from dataclasses import dataclass
import html
from typing import Iterable

from app.chapter_export.service import chinese_number


@dataclass(frozen=True)
class BookVolume:
    """卷的标题顺序信息。"""

    id: str
    title: str
    order: int


@dataclass(frozen=True)
class BookChapter:
    """按序组装用的章节信息（含正文）。"""

    id: str
    volume_id: str
    title: str
    content: str


def escape_text(value: str) -> str:
    return html.escape(value, quote=False)


def build_book_html(
    project_title: str,
    volumes: Iterable[BookVolume],
    chapters: Iterable[BookChapter],
    *,
    lang: str = "zh-CN",
) -> str:
    """把整本书组装成单个 HTML 文档字符串。"""
    volume_by_id = {volume.id: volume for volume in volumes}

    parts: list[str] = [
        "<!DOCTYPE html>",
        f'<html lang="{escape_text(lang)}">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>{escape_text(project_title)}</title>",
        "</head>",
        "<body>",
        f"<h1>{escape_text(project_title)}</h1>",
    ]

    last_volume_id: str | None = None
    for chapter in chapters:
        volume = volume_by_id.get(chapter.volume_id)
        if volume is not None and volume.id != last_volume_id:
            volume_label = f"第{chinese_number(volume.order)}卷" if volume.order > 0 else ""
            parts.append(
                f"<h2>{escape_text(volume_label)} {escape_text(volume.title)}</h2>"
            )
            last_volume_id = volume.id
        elif volume is None and last_volume_id is not None:
            # 章节挂载的卷缺失时避免沿用上一个卷标题。
            last_volume_id = None

        parts.append(f"<h3>{escape_text(chapter.title)}</h3>")
        parts.extend(_render_paragraphs(chapter.content))

    parts.append("</body>")
    parts.append("</html>")
    return "\n".join(parts)


def _render_paragraphs(content: str) -> list[str]:
    """把正文按空行分段，段内换行转 <br/>，逐段输出 <p>。"""
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs: list[str] = []
    for block in normalized.split("\n\n"):
        block = block.strip("\n").strip()
        if not block:
            continue
        lines = [escape_text(line) for line in block.split("\n")]
        inner = "<br/>".join(lines)
        paragraphs.append(f"<p>{inner}</p>")
    if not paragraphs:
        paragraphs.append("<p></p>")
    return paragraphs
