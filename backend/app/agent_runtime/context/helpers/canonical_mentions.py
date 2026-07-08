from __future__ import annotations

from dataclasses import dataclass
import html
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.repos.character_repo import get_by_id as get_character_by_id
from app.storage.repos.chapter_repo import get_by_id as get_chapter_by_id
from app.storage.repos.note_category_repo import (
    get_by_id as get_note_category_by_id,
)
from app.storage.repos.note_repo import get_by_id as get_note_by_id
from app.storage.repos.volume_repo import get_by_id as get_volume_by_id
from app.storage.repos.world_info_entry_repo import get_by_id as get_world_info_entry_by_id

_MENTION_RE = re.compile(
    r"<of-mention\b(?P<attrs_self>[^<>]*?)\s*/>"
    r"|<of-mention\b(?P<attrs_block>[^<>]*?)>(?P<body>.*?)</of-mention\s*>",
    re.DOTALL,
)
_ATTR_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)="([^"]*)"')

_KIND_ATTR_BY_ID_ATTR = (
    ("volume_id", "volume"),
    ("chapter_id", "chapter"),
    ("note_id", "note"),
    ("note_category_id", "note_category"),
    ("world_info_entry_id", "world_info_entry"),
    ("character_id", "character"),
)


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
    kind = _infer_kind(attrs)
    body = match.group("body") or ""
    return CanonicalMention(
        raw=raw,
        kind=kind,
        attrs=attrs,
        body=html.unescape(body),
    )


def _parse_attrs(raw_attrs: str) -> dict[str, str]:
    return {key: html.unescape(value) for key, value in _ATTR_RE.findall(raw_attrs)}


def _infer_kind(attrs: dict[str, str]) -> str:
    for attr_name, kind in _KIND_ATTR_BY_ID_ATTR:
        if attrs.get(attr_name, "").strip():
            return kind
    return attrs.get("kind", "").strip()


def _is_expanded_mention(mention: CanonicalMention) -> bool:
    return bool(
        mention.attrs.get("line_start", "").strip()
        and mention.attrs.get("line_end", "").strip()
    )


class _MentionResolver:
    def __init__(self, session: AsyncSession | None) -> None:
        self._session = session
        self._volume_cache: dict[str, str | None] = {}
        self._chapter_path_cache: dict[str, str | None] = {}
        self._note_cache: dict[str, str | None] = {}
        self._note_category_cache: dict[str, str | None] = {}
        self._world_info_entry_cache: dict[str, str | None] = {}
        self._character_cache: dict[str, str | None] = {}

    async def anchor_label(self, mention: CanonicalMention) -> str:
        fallback = _fallback_label(mention)
        if self._session is None:
            return fallback
        if mention.kind == "volume":
            volume_id = mention.attrs.get("volume_id", "").strip()
            if volume_id:
                return await self._resolve_volume_title(volume_id) or fallback
            return fallback
        if mention.kind == "chapter":
            chapter_id = mention.attrs.get("chapter_id", "").strip()
            if chapter_id:
                return await self._resolve_chapter_path(chapter_id) or fallback
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
        if mention.kind == "world_info_entry":
            entry_id = mention.attrs.get("world_info_entry_id", "").strip()
            if entry_id:
                return await self._resolve_world_info_entry_title(entry_id) or fallback
            return fallback
        if mention.kind == "character":
            character_id = mention.attrs.get("character_id", "").strip()
            if character_id:
                return await self._resolve_character_name(character_id) or fallback
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

    async def _resolve_chapter_path(self, chapter_id: str) -> str | None:
        if chapter_id in self._chapter_path_cache:
            return self._chapter_path_cache[chapter_id]
        session = self._session
        if session is None:
            return None
        chapter = await get_chapter_by_id(session, chapter_id)
        if chapter is None or not chapter.title:
            self._chapter_path_cache[chapter_id] = None
            return None
        chapter_title = chapter.title.strip()
        volume_title = await self._resolve_volume_title(chapter.volume_id)
        path = f"{volume_title}/{chapter_title}" if volume_title else chapter_title
        self._chapter_path_cache[chapter_id] = path
        return path

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

    async def _resolve_world_info_entry_title(self, entry_id: str) -> str | None:
        if entry_id in self._world_info_entry_cache:
            return self._world_info_entry_cache[entry_id]
        session = self._session
        if session is None:
            return None
        entry = await get_world_info_entry_by_id(session, entry_id)
        title = entry.name.strip() if entry and entry.name else None
        self._world_info_entry_cache[entry_id] = title
        return title

    async def _resolve_character_name(self, character_id: str) -> str | None:
        if character_id in self._character_cache:
            return self._character_cache[character_id]
        session = self._session
        if session is None:
            return None
        character = await get_character_by_id(session, character_id)
        name = character.name.strip() if character and character.name else None
        self._character_cache[character_id] = name
        return name


async def compile_canonical_mentions(
    text: str,
    session: AsyncSession | None = None,
) -> str:
    parts = parse_canonical_mentions(text)
    if len(parts) == 1 and parts[0] == text:
        return text

    resolver = _MentionResolver(session)
    compiled: list[str] = []

    for index, part in enumerate(parts):
        if isinstance(part, str):
            compiled.append(part)
            continue

        if _is_expanded_mention(part):
            if not compiled:
                compiled.append("\n")
            elif not compiled[-1].endswith("\n"):
                compiled.append("\n")
            compiled.append(await _compile_expanded_mention(part, resolver))
            continue

        compiled.append(await _compile_compact_mention(part, resolver))

    return "".join(compiled)


def _fallback_label(mention: CanonicalMention) -> str:
    if label := mention.attrs.get("label", "").strip():
        return label
    for attr_name, _kind in _KIND_ATTR_BY_ID_ATTR:
        if value := mention.attrs.get(attr_name, "").strip():
            return value
    return mention.raw


async def _compile_compact_mention(
    mention: CanonicalMention, resolver: _MentionResolver
) -> str:
    anchor = await _build_anchor(mention, resolver)
    if anchor is None:
        return mention.raw
    return f" {anchor} "


async def _compile_expanded_mention(
    mention: CanonicalMention, resolver: _MentionResolver
) -> str:
    anchor = await _build_anchor(mention, resolver, include_line_range=True)
    if anchor is None:
        return mention.raw
    body = re.sub(r"\s+", " ", mention.body).strip()
    return f"{anchor}\n```\n{body}\n```\n"


async def _build_anchor(
    mention: CanonicalMention,
    resolver: _MentionResolver,
    *,
    include_line_range: bool = False,
) -> str | None:
    if not mention.kind:
        return None
    display_label = (await resolver.anchor_label(mention)) or _fallback_label(mention)
    anchor = f"@{mention.kind}:{display_label}"
    if not include_line_range:
        return anchor

    start_line = mention.attrs.get("line_start", "").strip()
    end_line = mention.attrs.get("line_end", "").strip()
    if not start_line or not end_line:
        return anchor
    return f"{anchor}:{start_line}-{end_line}"
