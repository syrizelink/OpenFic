from __future__ import annotations

from dataclasses import dataclass
import html
import re
from collections.abc import Iterable


_SKILL_COMMAND_RE = re.compile(
    r"<of-skill\b(?P<attrs_self>[^<>]*?)\s*/>",
    re.DOTALL,
)
_ATTR_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)="([^"]*)"')


@dataclass(frozen=True)
class CanonicalSkillCommand:
    raw: str
    skill_id: str
    name: str


def parse_canonical_skill_commands(text: str) -> list[str | CanonicalSkillCommand]:
    if not text or "<of-skill" not in text:
        return [text]

    parts: list[str | CanonicalSkillCommand] = []
    cursor = 0
    for match in _SKILL_COMMAND_RE.finditer(text):
        if match.start() > cursor:
            parts.append(text[cursor : match.start()])
        attrs = _parse_attrs(match.group("attrs_self") or "")
        skill_id = attrs.get("id", "").strip()
        if not skill_id:
            parts.append(match.group(0))
            cursor = match.end()
            continue
        parts.append(
            CanonicalSkillCommand(
                raw=match.group(0),
                skill_id=skill_id,
                name=attrs.get("name", "").strip(),
            )
        )
        cursor = match.end()

    if cursor < len(text):
        parts.append(text[cursor:])
    return parts


def compile_canonical_commands(text: str) -> str:
    parts = parse_canonical_skill_commands(text)
    if len(parts) == 1 and parts[0] == text:
        return text

    compiled: list[str] = []
    for part in parts:
        if isinstance(part, str):
            compiled.append(part)
        elif part.name:
            compiled.append(f"@skill:{part.name}")
        else:
            compiled.append(f"@skill:{part.skill_id}")
    return "".join(compiled)


def extract_referenced_skill_ids(
    texts: Iterable[str],
) -> tuple[str, ...]:
    """提取 Skill 的稳定 ID；带 ID 的规范命令不依赖名称边界。"""
    referenced: list[str] = []
    for text in texts:
        for part in parse_canonical_skill_commands(text):
            if isinstance(part, CanonicalSkillCommand):
                _append_unique(referenced, part.skill_id)
    return tuple(referenced)


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def _parse_attrs(raw_attrs: str) -> dict[str, str]:
    return {key: html.unescape(value) for key, value in _ATTR_RE.findall(raw_attrs)}
