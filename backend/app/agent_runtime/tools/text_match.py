"""Fuzzy text matching for edit tools."""

from __future__ import annotations

import re
from dataclasses import dataclass

_LINE_SPLIT_RE = re.compile(r"[^\n]*\n|[^\n]+")


def normalize_for_fuzzy_match(text: str) -> str:
    """Normalize text for fuzzy matching.

    Strips trailing whitespace per line, and converts smart quotes, Unicode
    dashes and special spaces to ASCII. NFKC normalization is intentionally
    NOT applied: it would convert fullwidth CJK punctuation (，！？：； …) to
    halfwidth, corrupting Chinese prose style on the rewritten lines.
    """
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    # Smart single quotes -> '
    text = re.sub(r"[\u2018\u2019\u201A\u201B]", "'", text)
    # Smart double quotes -> "
    text = re.sub(r"[\u201C\u201D\u201E\u201F]", '"', text)
    # Various dashes/hyphens -> -
    # U+2010 hyphen, U+2011 non-breaking hyphen, U+2012 figure dash,
    # U+2013 en-dash, U+2014 em-dash, U+2015 horizontal bar, U+2212 minus
    text = re.sub(r"[\u2010\u2011\u2012\u2013\u2014\u2015\u2212]", "-", text)
    # Special spaces -> regular space
    # U+00A0 NBSP, U+2002-U+200A various spaces, U+202F narrow NBSP,
    # U+205F medium math space, U+3000 ideographic space
    text = re.sub(r"[\u00A0\u2002-\u200A\u202F\u205F\u3000]", " ", text)
    return text


def _split_lines_with_endings(content: str) -> list[str]:
    return _LINE_SPLIT_RE.findall(content)


def _get_line_spans(content: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    offset = 0
    for line in _split_lines_with_endings(content):
        spans.append((offset, offset + len(line)))
        offset = spans[-1][1]
    return spans


def _apply_replacements(
    content: str,
    replacements: list[tuple[int, int, str]],
    offset: int = 0,
) -> str:
    """Apply replacements (match_index, match_length, new_text) in reverse order."""
    result = content
    for match_index, match_length, new_text in reversed(replacements):
        idx = match_index - offset
        result = result[:idx] + new_text + result[idx + match_length:]
    return result


def _apply_replacements_preserving_unchanged(
    original_content: str,
    base_content: str,
    replacements: list[tuple[int, int, str]],
) -> str:
    """Apply replacements matched against ``base_content`` to ``original_content``.

    Each replacement is widened to the lines it touches, those touched lines
    are rewritten from the normalized base, and all other lines are copied back
    from ``original_content``. The actual replacement ranges drive preservation
    so duplicate normalized lines cannot be aligned to the wrong occurrence.

    Replacements must be processed in source order. A single monotonic line
    cursor advances across the sorted matches, so the whole pass is O(n) in the
    number of lines/matches instead of O(n^2).
    """
    original_lines = _split_lines_with_endings(original_content)
    base_spans = _get_line_spans(base_content)
    if len(original_lines) != len(base_spans):
        raise ValueError(
            "Cannot preserve unchanged lines: base content has a different line count."
        )
    line_ends = [e for _, e in base_spans]
    n_lines = len(base_spans)

    sorted_reps = sorted(replacements, key=lambda r: r[0])
    groups: list[dict] = []
    # Monotonic cursor: because replacements are sorted by match_index, the
    # containing line index never decreases across iterations.
    cursor = 0
    for rep in sorted_reps:
        match_index, match_length, _ = rep
        match_end = match_index + match_length
        # Advance the cursor to the line containing match_index.
        while cursor < n_lines and line_ends[cursor] <= match_index:
            cursor += 1
        if cursor >= n_lines:
            raise ValueError("Replacement range is outside the base content.")
        start_line = cursor
        # The end line is >= start_line; advance a separate cursor so the outer
        # cursor stays valid for subsequent (later) replacements.
        end_cursor = cursor
        while end_cursor < n_lines and line_ends[end_cursor] < match_end:
            end_cursor += 1
        if end_cursor >= n_lines:
            raise ValueError("Replacement range is outside the base content.")
        end_line = end_cursor + 1
        if groups and start_line < groups[-1]["end_line"]:
            groups[-1]["end_line"] = max(groups[-1]["end_line"], end_line)
            groups[-1]["replacements"].append(rep)
            continue
        groups.append(
            {"start_line": start_line, "end_line": end_line, "replacements": [rep]}
        )
    # Collect fragments into a list and join once at the end. Repeated
    # ``result += ...`` would copy the growing accumulator on every group,
    # degrading to O(n^2) when ``replace_all`` produces many groups.
    fragments: list[str] = []
    original_line_index = 0
    for group in groups:
        fragments.append(
            "".join(original_lines[original_line_index:group["start_line"]])
        )
        group_start_offset = base_spans[group["start_line"]][0]
        group_end_offset = base_spans[group["end_line"] - 1][1]
        fragments.append(
            _apply_replacements(
                base_content[group_start_offset:group_end_offset],
                group["replacements"],
                group_start_offset,
            )
        )
        original_line_index = group["end_line"]
    fragments.append("".join(original_lines[original_line_index:]))
    return "".join(fragments)


@dataclass(frozen=True)
class FuzzyReplaceResult:
    new_content: str
    used_fuzzy_match: bool


def _query_had_stripped_trailing_whitespace(text: str) -> bool:
    """Return whether normalization stripped trailing whitespace from the
    last line of ``text`` (already LF-normalized).

    Stripping the query's last line can turn it into a *prefix* of a longer
    run in the content -- e.g. query ``"foo "`` matching the ``"foo"`` head
    of ``"foobar"`` -- which would let a sloppy query silently rewrite text
    the agent never quoted, so such matches must be boundary-checked. Only the
    final line's trailing whitespace matters: a query ending in a newline
    keeps that newline verbatim in normalized form, so it cannot create a
    prefix.
    """
    last_line = text.rsplit("\n", 1)[-1]
    return bool(last_line) and last_line != last_line.rstrip()


def _match_end_is_whitespace_or_end(content: str, pos: int, length: int) -> bool:
    """Return whether ``pos`` is at or past the end of ``content`` or points at
    a whitespace character."""
    return pos >= length or content[pos].isspace()


def _decode_escaped_whitespace(text: str) -> str | None:
    """Decode an escaped whitespace-only value produced by tool-calling models."""
    decoded: list[str] = []
    found_escape = False
    index = 0
    while index < len(text):
        char = text[index]
        if char.isspace():
            decoded.append(char)
            index += 1
            continue
        if char != "\\" or index + 1 >= len(text):
            return None
        escaped = text[index + 1]
        replacement = {"n": "\n", "r": "\r", "t": "\t"}.get(escaped)
        if replacement is None:
            return None
        decoded.append(replacement)
        found_escape = True
        index += 2
    return "".join(decoded) if found_escape else None


def _replace_escaped_whitespace(
    content: str,
    old_text: str,
    new_text: str,
    *,
    replace_all: bool,
) -> FuzzyReplaceResult | None:
    decoded_old_text = _decode_escaped_whitespace(old_text)
    if decoded_old_text is None:
        return None
    decoded_new_text = _decode_escaped_whitespace(new_text) or new_text
    return fuzzy_replace(
        content,
        decoded_old_text,
        decoded_new_text,
        replace_all=replace_all,
    )


def fuzzy_replace(
    content: str,
    old_text: str,
    new_text: str,
    *,
    replace_all: bool = False,
) -> FuzzyReplaceResult | None:
    """Find ``old_text`` in ``content`` and replace it with ``new_text``.

    Exact match is attempted first. If that fails, a fuzzy match is attempted
    by normalizing both texts (see :func:`normalize_for_fuzzy_match`). When
    fuzzy matching is used, unchanged line blocks are preserved from the
    original content so only the touched lines are rewritten from the
    normalized space.

    Returns ``None`` if ``old_text`` cannot be found (even after fuzzy
    normalization). Raises ``ValueError`` if ``old_text`` is empty.
    """
    if not old_text:
        raise ValueError("old_text must not be empty")

    # Normalize line endings to LF first (mirrors Pi's normalizeToLF).
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    old_text = old_text.replace("\r\n", "\n").replace("\r", "\n")
    new_text = new_text.replace("\r\n", "\n").replace("\r", "\n")

    # 1. Exact match
    exact_index = content.find(old_text)
    if exact_index != -1:
        if replace_all:
            new_content = content.replace(old_text, new_text)
        else:
            new_content = content.replace(old_text, new_text, 1)
        return FuzzyReplaceResult(new_content, used_fuzzy_match=False)

    # 2. Fuzzy match - work in normalized space
    fuzzy_content = normalize_for_fuzzy_match(content)
    fuzzy_old_text = normalize_for_fuzzy_match(old_text)

    # A whitespace-only query (spaces, tabs, line-trailing whitespace) collapses
    # to an empty string after normalization. ``find("")`` would match at every
    # position -- corrupting content with ``replace_all=False`` and looping
    # forever with ``replace_all=True``. Treat it as "not found".
    if not fuzzy_old_text:
        return _replace_escaped_whitespace(
            content, old_text, new_text, replace_all=replace_all
        )

    # When the query's trailing whitespace was stripped by normalization,
    # ``fuzzy_old_text`` may be a *prefix* of a longer run in the content --
    # e.g. query ``"foo "`` matches the ``"foo"`` head of ``"foobar"`` --
    # which would let a sloppy query silently rewrite text the agent never
    # quoted. Guard such matches: the content must continue with whitespace
    # (or end) right after the match, so the stripped trailing whitespace still
    # aligns with real whitespace in the original. Otherwise the match is a
    # prefix artifact and is skipped; if none survive, the call is "not found".
    boundary_check = _query_had_stripped_trailing_whitespace(old_text)
    fuzzy_len = len(fuzzy_old_text)
    content_len = len(fuzzy_content)

    replacements: list[tuple[int, int, str]] = []
    start = 0
    while True:
        idx = fuzzy_content.find(fuzzy_old_text, start)
        if idx == -1:
            break
        match_end = idx + fuzzy_len
        if boundary_check and not _match_end_is_whitespace_or_end(
            fuzzy_content, match_end, content_len
        ):
            # Prefix artifact: keep scanning for a genuine occurrence.
            start = idx + 1
            continue
        replacements.append((idx, fuzzy_len, new_text))
        if not replace_all:
            break
        start = match_end

    if not replacements:
        return _replace_escaped_whitespace(
            content, old_text, new_text, replace_all=replace_all
        )

    new_content = _apply_replacements_preserving_unchanged(
        content, fuzzy_content, replacements
    )
    return FuzzyReplaceResult(new_content, used_fuzzy_match=True)
