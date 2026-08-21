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
        parts.append(
            CanonicalSkillCommand(
                raw=match.group(0),
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
            compiled.append(part.raw)
    return "".join(compiled)


def extract_referenced_skill_names(
    texts: Iterable[str],
    available_names: Iterable[str],
) -> tuple[str, ...]:
    names = tuple(dict.fromkeys(name.strip() for name in available_names if name.strip()))
    if not names:
        return ()

    referenced: list[str] = []
    for text in texts:
        compiled = compile_canonical_commands(text)
        cursor = 0
        while (marker_start := compiled.find("@skill:", cursor)) >= 0:
            suffix = compiled[marker_start + len("@skill:") :]
            matches = [name for name in names if suffix.startswith(name)]
            if matches:
                name = max(matches, key=len)
                if name not in referenced:
                    referenced.append(name)
                cursor = marker_start + len("@skill:") + len(name)
            else:
                cursor = marker_start + len("@skill:")
    return tuple(referenced)


def _parse_attrs(raw_attrs: str) -> dict[str, str]:
    return {key: html.unescape(value) for key, value in _ATTR_RE.findall(raw_attrs)}

