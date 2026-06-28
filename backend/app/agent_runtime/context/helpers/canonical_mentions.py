from __future__ import annotations

from dataclasses import dataclass
import html
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.repos.chapter_repo import get_by_id as get_chapter_by_id
from app.storage.repos.note_category_repo import (
    get_by_id as get_note_category_by_id,
)
from app.storage.repos.note_repo import get_by_id as get_note_by_id
from app.storage.repos.volume_repo import get_by_id as get_volume_by_id

_MENTION_RE = re.compile(
    r"<of-mention\b(?P<attrs_self>[^<>]*?)\s*/>"
    r"|<of-mention\b(?P<attrs_block>[^<>]*?)>(?P<body>.*?)</of-mention\s*>",
    re.DOTALL,
)
_ATTR_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)="([^"]*)"')


@dataclass(frozen=True)
class CanonicalMention:
    raw: str
    kind: str
    attrs: dict[str, str]
    body: str = ""


def parse_canonical_mentions(text: str) -> list[str | CanonicalMention]:
    if not text or "<of-mention" not in text:
        return [text]

    parts: list[str | CanonicalMention] = []
    cursor = 0
    for match in _MENTION_RE.finditer(text):
        if match.start() > cursor:
            parts.append(text[cursor : match.start()])
        parts.append(_match_to_mention(match))
        cursor = match.end()
    if cursor < len(text):
        parts.append(text[cursor:])
    return parts


def _match_to_mention(match: re.Match[str]) -> CanonicalMention:
    raw = match.group(0)
    attrs = _parse_attrs(match.group("attrs_self") or match.group("attrs_block") or "")
    kind = attrs.get("kind", "")
    body = match.group("body") or ""
    return CanonicalMention(
        raw=raw,
        kind=kind,
        attrs=attrs,
        body=html.unescape(body),
    )


def _parse_attrs(raw_attrs: str) -> dict[str, str]:
    return {key: html.unescape(value) for key, value in _ATTR_RE.findall(raw_attrs)}


class _MentionResolver:
    def __init__(self, session: AsyncSession | None) -> None:
        self._session = session
        self._volume_cache: dict[str, str | None] = {}
        self._chapter_cache: dict[str, str | None] = {}
        self._note_cache: dict[str, str | None] = {}
        self._note_category_cache: dict[str, str | None] = {}

    async def display_label(self, mention: CanonicalMention) -> str:
        fallback = mention.attrs.get("label", "").strip()
        if self._session is None:
            return fallback
        if mention.kind == "volume":
            volume_id = mention.attrs.get("volume_id", "").strip()
            if volume_id:
                return await self._resolve_volume_title(volume_id) or fallback
            return fallback
        if mention.kind in {"chapter", "line_range"}:
            chapter_id = mention.attrs.get("chapter_id", "").strip()
            if chapter_id:
                return await self._resolve_chapter_title(chapter_id) or fallback
            return fallback
        if mention.kind == "note":
            note_id = mention.attrs.get("note_id", "").strip()
            if note_id:
                return await self._resolve_note_title(note_id) or fallback
            return fallback
        if mention.kind == "note_category":
            category_id = mention.attrs.get("note_category_id", "").strip()
            if category_id:
                return await self._resolve_note_category_title(category_id) or fallback
            return fallback
        return fallback

    async def _resolve_volume_title(self, volume_id: str) -> str | None:
        if volume_id in self._volume_cache:
            return self._volume_cache[volume_id]
        session = self._session
        if session is None:
            return None
        volume = await get_volume_by_id(session, volume_id)
        title = volume.title.strip() if volume and volume.title else None
        self._volume_cache[volume_id] = title
        return title

    async def _resolve_chapter_title(self, chapter_id: str) -> str | None:
        if chapter_id in self._chapter_cache:
            return self._chapter_cache[chapter_id]
        session = self._session
        if session is None:
            return None
        chapter = await get_chapter_by_id(session, chapter_id)
        title = chapter.title.strip() if chapter and chapter.title else None
        self._chapter_cache[chapter_id] = title
        return title

    async def _resolve_note_title(self, note_id: str) -> str | None:
        if note_id in self._note_cache:
            return self._note_cache[note_id]
        session = self._session
        if session is None:
            return None
        note = await get_note_by_id(session, note_id)
        title = note.title.strip() if note and note.title else None
        self._note_cache[note_id] = title
        return title

    async def _resolve_note_category_title(self, category_id: str) -> str | None:
        if category_id in self._note_category_cache:
            return self._note_category_cache[category_id]
        session = self._session
        if session is None:
            return None
        category = await get_note_category_by_id(session, category_id)
        title = category.title.strip() if category and category.title else None
        self._note_category_cache[category_id] = title
        return title


async def compile_canonical_mentions(
    text: str,
    session: AsyncSession | None = None,
) -> str:
    parts = parse_canonical_mentions(text)
    if len(parts) == 1 and parts[0] == text:
        return text

    resolver = _MentionResolver(session)
    compiled: list[str] = []
    pending_quote_lines: list[str] = []

    def _trim_trailing_inline_space() -> None:
        if not compiled:
            return
        compiled[-1] = compiled[-1].rstrip(" \t")
        if not compiled[-1]:
            compiled.pop()

    def _flush_pending_quotes(next_text: str | None = None) -> None:
        nonlocal pending_quote_lines
        if not pending_quote_lines:
            return
        _trim_trailing_inline_space()
        if compiled and not compiled[-1].endswith("\n"):
            compiled.append("\n")
        compiled.append("\n".join(f"> {line}" for line in pending_quote_lines))
        if next_text is not None and not next_text.startswith("\n"):
            compiled.append("\n")
        pending_quote_lines = []

    for part in parts:
        if isinstance(part, str):
            if not part.strip():
                continue
            _flush_pending_quotes(part)
            compiled.append(part)
            continue
        rendered = await _compile_mention(part, resolver)
        pending_quote_lines.append(rendered)
    _flush_pending_quotes()
    return "".join(compiled)


async def _compile_mention(
    mention: CanonicalMention, resolver: _MentionResolver
) -> str:
    display_label = (await resolver.display_label(mention)) or mention.raw

    if mention.kind == "volume":
        return f"引用卷：{display_label}"
    if mention.kind == "chapter":
        return f"引用章节：{display_label}"
    if mention.kind == "note":
        return f"引用笔记：{display_label}"
    if mention.kind == "note_category":
        return f"引用笔记分类：{display_label}"
    if mention.kind == "line_range":
        start_line = mention.attrs.get("start_line", "").strip()
        end_line = mention.attrs.get("end_line", "").strip()
        snapshot_text = re.sub(r"\s+", " ", mention.body).strip()
        prefix = f"引用片段：{display_label} 第{start_line}-{end_line}行"
        if snapshot_text:
            return f"{prefix}；原文快照：{snapshot_text}"
        return prefix
    return mention.raw
