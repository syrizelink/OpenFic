"""Tests for :mod:`app.agent_runtime.tools.text_match`."""

import pytest

from app.agent_runtime.tools.text_match import (
    FuzzyReplaceResult,
    fuzzy_replace,
    normalize_for_fuzzy_match,
)


# ---------------------------------------------------------------------------
# normalize_for_fuzzy_match
# ---------------------------------------------------------------------------


def test_normalize_strips_trailing_whitespace_per_line() -> None:
    assert normalize_for_fuzzy_match("hello   \nworld\t\n") == "hello\nworld\n"


def test_normalize_converts_smart_single_quotes() -> None:
    assert normalize_for_fuzzy_match("\u2018a\u2019") == "'a'"


def test_normalize_converts_smart_double_quotes() -> None:
    assert normalize_for_fuzzy_match("\u201ca\u201d") == '"a"'


def test_normalize_converts_unicode_dashes_to_hyphen() -> None:
    for dash in "\u2010\u2011\u2012\u2013\u2014\u2015\u2212":
        assert normalize_for_fuzzy_match(f"a{dash}b") == "a-b"


def test_normalize_converts_special_spaces_to_regular_space() -> None:
    for space in "\u00a0\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f\u3000":
        assert normalize_for_fuzzy_match(f"a{space}b") == "a b"


def test_normalize_preserves_cjk_fullwidth_punctuation() -> None:
    # NFKC is intentionally NOT applied so CJK style is preserved.
    assert normalize_for_fuzzy_match("你好，世界！") == "你好，世界！"


def test_normalize_keeps_regular_text_intact() -> None:
    assert normalize_for_fuzzy_match("plain text\nline two") == "plain text\nline two"


# ---------------------------------------------------------------------------
# fuzzy_replace - exact match path
# ---------------------------------------------------------------------------


def test_exact_match_replaces_first_occurrence_only() -> None:
    result = fuzzy_replace("a a a", "a", "b")
    assert result == FuzzyReplaceResult("b a a", used_fuzzy_match=False)


def test_exact_match_replace_all_replaces_every_occurrence() -> None:
    result = fuzzy_replace("a a a", "a", "b", replace_all=True)
    assert result == FuzzyReplaceResult("b b b", used_fuzzy_match=False)


def test_exact_match_takes_precedence_over_fuzzy() -> None:
    # The old text contains a smart quote but appears verbatim in the content,
    # so the exact path is used and quotes are left untouched.
    content = "say \u201chello\u201d"
    result = fuzzy_replace(content, "\u201chello\u201d", "hi")
    assert result == FuzzyReplaceResult("say hi", used_fuzzy_match=False)


def test_returns_none_when_no_match() -> None:
    assert fuzzy_replace("hello world", "missing", "x") is None


def test_fuzzy_no_match_returns_none() -> None:
    # Smart-quote normalization cannot bridge a real textual difference.
    assert fuzzy_replace("hello world", "goodbye", "x") is None


def test_empty_old_text_raises() -> None:
    with pytest.raises(ValueError):
        fuzzy_replace("content", "", "new")


# ---------------------------------------------------------------------------
# fuzzy_replace - fuzzy match path
# ---------------------------------------------------------------------------


def test_fuzzy_match_smart_quotes() -> None:
    # Content uses smart quotes; old_text uses ASCII quotes. The fuzzy path
    # normalizes both for matching and rewrites the touched (single) line from
    # the normalized base, while ``new_text`` is inserted verbatim.
    result = fuzzy_replace("前缀\u201c引文\u201d后缀", '"引文"', "X")
    assert result == FuzzyReplaceResult("前缀X后缀", used_fuzzy_match=True)


def test_fuzzy_match_special_spaces() -> None:
    result = fuzzy_replace("间距\u3000很大", "间距 很大", "no space")
    assert result == FuzzyReplaceResult("no space", used_fuzzy_match=True)


def test_fuzzy_match_dashes() -> None:
    result = fuzzy_replace("a\u2014b", "a-b", "X")
    assert result == FuzzyReplaceResult("X", used_fuzzy_match=True)


def test_fuzzy_match_used_fuzzy_match_flag_true() -> None:
    result = fuzzy_replace("a\u00a0b", "a b", "c")
    assert result == FuzzyReplaceResult("c", used_fuzzy_match=True)


def test_fuzzy_match_preserves_unchanged_lines() -> None:
    # The untouched first line keeps its NBSP and trailing whitespace; only the
    # touched line (which requires fuzzy matching via its NBSP) is rewritten
    # from the normalized base.
    content = "keep\u00a0me   \nchange\u00a0me\n"
    result = fuzzy_replace(content, "change me", "CHANGED")
    assert result == FuzzyReplaceResult(
        "keep\u00a0me   \nCHANGED\n", used_fuzzy_match=True
    )


def test_fuzzy_match_preserves_unchanged_lines_multi_replacement() -> None:
    content = "line\u00a0one   \ntar\u00a0get\ntwo tar\u00a0get\nend"
    result = fuzzy_replace(content, "tar get", "T", replace_all=True)
    assert result == FuzzyReplaceResult(
        "line\u00a0one   \nT\ntwo T\nend", used_fuzzy_match=True
    )


def test_fuzzy_match_replace_all() -> None:
    # Two non-overlapping fuzzy matches on a single line.
    result = fuzzy_replace("x\u00a0x and x\u00a0x", "x x", "y", replace_all=True)
    assert result == FuzzyReplaceResult("y and y", used_fuzzy_match=True)


def test_fuzzy_match_single_when_replace_all_false() -> None:
    # Only the first occurrence is replaced; the untouched second line keeps
    # its original NBSP and trailing whitespace.
    content = "x\u00a0x\u00a0x\nkeep\u00a0me   "
    result = fuzzy_replace(content, "x x", "y", replace_all=False)
    assert result == FuzzyReplaceResult(
        "y x\nkeep\u00a0me   ", used_fuzzy_match=True
    )


def test_fuzzy_match_spans_multiple_lines() -> None:
    content = "alpha\u00a0beta\n.gamma.\ngamma"
    result = fuzzy_replace(content, "alpha beta\n.gamma.", "REPLACED")
    assert result == FuzzyReplaceResult("REPLACED\ngamma", used_fuzzy_match=True)


# ---------------------------------------------------------------------------
# fuzzy_replace - line ending normalization
# ---------------------------------------------------------------------------


def test_crlf_in_content_is_normalized_for_matching() -> None:
    result = fuzzy_replace("line1\r\nline2", "line1\nline2", "X")
    assert result == FuzzyReplaceResult("X", used_fuzzy_match=False)


def test_cr_in_old_text_is_normalized() -> None:
    result = fuzzy_replace("a\nb", "a\rb", "X")
    assert result == FuzzyReplaceResult("X", used_fuzzy_match=False)


def test_crlf_normalization_with_fuzzy_match() -> None:
    content = "a\u00a0b\r\nc"
    result = fuzzy_replace(content, "a b\nc", "X")
    assert result == FuzzyReplaceResult("X", used_fuzzy_match=True)


# ---------------------------------------------------------------------------
# fuzzy_replace - edge cases
# ---------------------------------------------------------------------------


def test_match_at_start_of_content() -> None:
    assert fuzzy_replace("abc rest", "abc", "X") == FuzzyReplaceResult(
        "X rest", used_fuzzy_match=False
    )


def test_match_at_end_of_content() -> None:
    assert fuzzy_replace("rest abc", "abc", "X") == FuzzyReplaceResult(
        "rest X", used_fuzzy_match=False
    )


def test_new_text_can_contain_normalized_chars() -> None:
    # The replacement text is inserted verbatim, not re-normalized.
    result = fuzzy_replace("a b", "a b", "\u201cquote\u201d")
    assert result == FuzzyReplaceResult("\u201cquote\u201d", used_fuzzy_match=False)


def test_duplicate_normalized_line_aligned_by_range() -> None:
    # Two lines that are identical after normalization. ``replace_all=False``
    # must touch only the first occurrence (aligned by the actual match range,
    # not by re-scanning), and the second untouched line keeps its smart
    # quotes verbatim.
    content = "a\u201cdup\u201d   \na\u201cdup\u201d\n"
    result = fuzzy_replace(content, 'a"dup"', "X", replace_all=False)
    assert result == FuzzyReplaceResult(
        "X\na\u201cdup\u201d\n", used_fuzzy_match=True
    )


# ---------------------------------------------------------------------------
# fuzzy_replace - whitespace-only old_text collapses to empty (regression)
# ---------------------------------------------------------------------------


def test_tab_old_text_not_in_content_returns_none() -> None:
    # Regression: "\t" normalizes to ""; find("") must not match the start of
    # the content and insert new_text before the original text.
    assert fuzzy_replace("今晚月色很好。", "\t", "月色") is None


def test_space_old_text_not_in_content_returns_none() -> None:
    assert fuzzy_replace("今晚月色很好。", " ", "月色") is None


def test_whitespace_only_old_text_replace_all_returns_none() -> None:
    # Regression: replace_all=True with a whitespace-only query previously
    # looped forever because start never advanced past idx 0.
    assert fuzzy_replace("今晚月色很好。", " ", "月色", replace_all=True) is None


def test_whitespace_old_text_present_in_content_still_exact_matches() -> None:
    # A real space in the content is a legitimate exact match and must still
    # be replaced (first occurrence only); only the normalized-empty path is
    # rejected.
    result = fuzzy_replace("a b c", " ", "-")
    assert result == FuzzyReplaceResult("a-b c", used_fuzzy_match=False)


def test_whitespace_old_text_exact_match_replace_all() -> None:
    result = fuzzy_replace("a b a b", " ", "-", replace_all=True)
    assert result == FuzzyReplaceResult("a-b-a-b", used_fuzzy_match=False)


# ---------------------------------------------------------------------------
# fuzzy_replace - replace_all fuzzy path must be linear (regression)
# ---------------------------------------------------------------------------


def test_replace_all_fuzzy_many_matches_is_linear() -> None:
    # Regression: _apply_replacements_preserving_unchanged used to accumulate
    # via ``result += ...``, making replace_all fuzzy replacement O(n^2). With
    # ~5000 smart-quoted lines this must finish near-instantly and yield the
    # exact expected result.
    n = 5000
    content = "\n".join("\u201ca\u201d" for _ in range(n))
    result = fuzzy_replace(content, '"a"', "b", replace_all=True)
    assert result is not None
    assert result.used_fuzzy_match is True
    assert result.new_content == "\n".join("b" for _ in range(n))
