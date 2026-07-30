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
# fuzzy_replace - escaped whitespace fallback
# ---------------------------------------------------------------------------


def test_escaped_newlines_replace_blank_lines() -> None:
    result = fuzzy_replace("11\n\n11\n\n111", r"\n\n", r"\n", replace_all=True)
    assert result == FuzzyReplaceResult("11\n11\n111", used_fuzzy_match=False)


@pytest.mark.parametrize(
    ("old_text", "actual_old_text", "new_text", "expected_new_text"),
    [
        (r"\n", "\n", r"\t", "\t"),
        (r"\t", "\t", r"\r", "\n"),
        (r"\r", "\r", r"\n", "\n"),
    ],
)
def test_escaped_whitespace_sequences_are_decoded_for_search_and_replacement(
    old_text: str,
    actual_old_text: str,
    new_text: str,
    expected_new_text: str,
) -> None:
    result = fuzzy_replace(f"before{actual_old_text}after", old_text, new_text)
    assert result == FuzzyReplaceResult(
        f"before{expected_new_text}after", used_fuzzy_match=False
    )


@pytest.mark.parametrize(
    ("content", "old_text"),
    [
        ("start\n end", r"\n "),
        ("start \nend", r" \n"),
    ],
)
def test_escaped_newline_with_surrounding_space_replaces_as_whitespace(
    content: str,
    old_text: str,
) -> None:
    result = fuzzy_replace(content, old_text, "0")
    assert result == FuzzyReplaceResult("start0end", used_fuzzy_match=False)


@pytest.mark.parametrize(
    ("old_text", "new_text"),
    [
        (r"\n", r"\t"),
        (r"\t", r"\r"),
        (r"\r", r"\n"),
    ],
)
def test_literal_escaped_whitespace_takes_precedence_over_fallback(
    old_text: str,
    new_text: str,
) -> None:
    result = fuzzy_replace(old_text, old_text, new_text)
    assert result == FuzzyReplaceResult(new_text, used_fuzzy_match=False)


def test_mixed_text_and_escaped_newline_is_not_decoded() -> None:
    assert fuzzy_replace("start\nend", r"start\nend", "X") is None


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


# ---------------------------------------------------------------------------
# fuzzy_replace - stripped trailing whitespace must not match a prefix
# ---------------------------------------------------------------------------


def test_query_trailing_space_does_not_match_prefix() -> None:
    # Regression: the agent quoted "foo " but the content is "foobar" with no
    # space after "foo". Stripping the query's trailing space used to turn it
    # into a prefix match, rewriting "foo" and leaving the dangling "bar"
    # appended to the new text ("Xbar"). It must now be reported as not found.
    assert fuzzy_replace("foobar", "foo ", "X") is None


def test_query_trailing_space_does_not_match_prefix_cjk() -> None:
    # The exact scenario from the bug report: "角色代号：foo " (trailing space)
    # must not match the "角色代号：foo" head of "角色代号：foobar".
    assert (
        fuzzy_replace("角色代号：foobar", "角色代号：foo ", "角色代号：已修正") is None
    )


def test_query_trailing_space_aligns_with_content_trailing_ws() -> None:
    # The content has trailing NBSP after "foo"; the agent used a regular
    # trailing space. After normalization both collapse, and the match ends at
    # the end of content -- a genuine boundary, not a prefix artifact -- so the
    # replacement is allowed. The boundary guard must not over-reject here.
    result = fuzzy_replace("foo\u00a0", "foo ", "X")
    assert result == FuzzyReplaceResult("X", used_fuzzy_match=True)


def test_query_trailing_space_aligns_with_content_interior_ws() -> None:
    # The content has an interior NBSP (foo + NBSP + bar); the agent's trailing
    # space aligns with that whitespace after "foo", so the match is genuine.
    # Only "foo" is rewritten; the whitespace and "bar" are preserved.
    result = fuzzy_replace("foo\u00a0bar", "foo ", "X")
    assert result == FuzzyReplaceResult("X bar", used_fuzzy_match=True)


def test_query_trailing_space_skips_prefix_keeps_genuine_single() -> None:
    # replace_all=False: the leftmost "代号：foo" is a prefix of "代号：foobar"
    # (artifact) and must be skipped; the genuine occurrence on line 2 (followed
    # by trailing NBSP, which aligns with the query's trailing space) is matched
    # instead, and the prefix line is left untouched.
    content = "角色代号：foobar\n代号：foo\u00a0"
    result = fuzzy_replace(content, "代号：foo ", "代号：已修正")
    assert result == FuzzyReplaceResult(
        "角色代号：foobar\n代号：已修正", used_fuzzy_match=True
    )


def test_query_trailing_space_skips_prefix_keeps_genuine_replace_all() -> None:
    # replace_all=True: line 1 (interior NBSP) and line 3 (trailing NBSP) are
    # genuine matches; line 2 ("foobar") is a prefix artifact and is skipped,
    # so its text is preserved verbatim.
    content = "foo\u00a0bar\nfoobar\nfoo\u00a0"
    result = fuzzy_replace(content, "foo ", "X", replace_all=True)
    assert result == FuzzyReplaceResult("X bar\nfoobar\nX", used_fuzzy_match=True)


def test_query_without_trailing_space_still_matches_prefix_normally() -> None:
    # No trailing whitespace is stripped from the query, so the boundary guard
    # is not engaged. A genuine fuzzy match (smart quote) still works even
    # though the normalized query is a prefix of the longer content line.
    result = fuzzy_replace("a\u201cb\u201drest", '"b"', "X")
    assert result == FuzzyReplaceResult("aXrest", used_fuzzy_match=True)


def test_query_trailing_space_replace_all_all_artifacts_returns_none() -> None:
    # Every occurrence of "foo" is a prefix of a longer run, so none survive the
    # boundary guard; the call is "not found" rather than corrupting content.
    assert fuzzy_replace("foobar\nfoobaz", "foo ", "X", replace_all=True) is None
