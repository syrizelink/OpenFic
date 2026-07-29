"""Shared limits for persisted editor content."""

MAX_EDITOR_CONTENT_LINES = 2_000
MAX_EDITOR_CONTENT_CHARACTERS = 100_000


class EditorContentLimitError(ValueError):
    """Raised when persisted editor content exceeds its supported size."""


def count_editor_content_lines(content: str) -> int:
    """Count logical lines without treating a trailing newline as an extra line."""
    return len(content.splitlines())


def validate_editor_content(content: str) -> None:
    """Raise when content exceeds the supported line or character limit."""
    line_count = count_editor_content_lines(content)
    character_count = len(content)
    if (
        line_count <= MAX_EDITOR_CONTENT_LINES
        and character_count <= MAX_EDITOR_CONTENT_CHARACTERS
    ):
        return

    raise EditorContentLimitError(
        "内容超出限制："
        f"当前 {line_count} 行、{character_count} 字符；"
        f"单一内容最多允许 {MAX_EDITOR_CONTENT_LINES} 行且 "
        f"{MAX_EDITOR_CONTENT_CHARACTERS} 字符。请拆分内容后重试。"
    )
