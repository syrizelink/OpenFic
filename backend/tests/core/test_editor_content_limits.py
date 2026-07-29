import pytest

from app.core.editor_content_limits import (
    MAX_EDITOR_CONTENT_CHARACTERS,
    MAX_EDITOR_CONTENT_LINES,
    EditorContentLimitError,
    count_editor_content_lines,
    validate_editor_content,
)


def test_count_editor_content_lines_treats_empty_text_as_zero_lines() -> None:
    assert count_editor_content_lines("") == 0


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_count_editor_content_lines_uses_consistent_newline_semantics(newline: str) -> None:
    assert count_editor_content_lines(f"first{newline}second{newline}") == 2


def test_validate_editor_content_accepts_limit_boundaries() -> None:
    validate_editor_content("\n".join("x" for _ in range(MAX_EDITOR_CONTENT_LINES)))
    validate_editor_content("x" * MAX_EDITOR_CONTENT_CHARACTERS)


def test_validate_editor_content_rejects_content_exceeding_line_limit() -> None:
    content = "\n".join("x" for _ in range(MAX_EDITOR_CONTENT_LINES + 1))

    with pytest.raises(EditorContentLimitError, match="2001 行"):
        validate_editor_content(content)


def test_validate_editor_content_rejects_content_exceeding_character_limit() -> None:
    content = "😀" * (MAX_EDITOR_CONTENT_CHARACTERS + 1)

    with pytest.raises(EditorContentLimitError, match="100001 字符"):
        validate_editor_content(content)
