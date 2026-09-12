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
        "Konten melebihi batas: "
        f"saat ini {line_count} baris, {character_count} karakter; "
        f"satu konten maksimum {MAX_EDITOR_CONTENT_LINES} baris dan "
        f"{MAX_EDITOR_CONTENT_CHARACTERS} karakter. Pecah konten lalu coba lagi."
    )
