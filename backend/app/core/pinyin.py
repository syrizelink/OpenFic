# -*- coding: utf-8 -*-
"""Utilities for Chinese pinyin search and ordering."""

from functools import lru_cache

from pypinyin import Style, lazy_pinyin


@lru_cache(maxsize=4096)
def _pinyin_parts(text: str) -> tuple[str, ...]:
    """Convert text into lower-case, tone-free pinyin syllables."""
    return tuple(
        part.lower()
        for part in lazy_pinyin(
            text,
            style=Style.NORMAL,
            errors=lambda characters: characters,
        )
    )


def to_pinyin(text: str | None) -> str:
    """Return compact pinyin while preserving non-Chinese characters."""
    if not text:
        return ""
    return "".join(_pinyin_parts(text))


def to_pinyin_initials(text: str | None) -> str:
    """Return the first character of each pinyin syllable."""
    if not text:
        return ""
    return "".join(part[0] for part in _pinyin_parts(text) if part)
