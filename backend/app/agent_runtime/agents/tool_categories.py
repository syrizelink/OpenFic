"""Tool category registry for PA/SA agent definitions."""

from collections.abc import Iterable, Mapping
from types import MappingProxyType


# Dulu ``search_chapters`` dan ``update_index`` dikecualikan pada mode cloud-only
# karena pustaka vektor native tidak dapat dimuat. Kini keduanya tersedia di semua
# mode: adapter SQLite FTS5 menangani pencarian kata kunci tanpa dependensi
# native. Himpunan ini disengaja kosong dan dipertahankan sebagai titik tunggal
# bila kelak ada tool yang benar-benar khusus lokal.
LOCAL_ONLY_TOOL_NAMES: frozenset[str] = frozenset()


TOOL_CATEGORIES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "orchestration": (
            "dispatch_subagent",
            "list_subagents",
            "notify_subagent",
            "recycle_subagent",
        ),
        "interaction": ("ask_user",),
        "web_search": ("web_search",),
        "web_fetch": ("web_fetch",),
        "plan": ("write_plan",),
        "chapter_read": (
            "list_volumes",
            "list_chapters",
            "read_chapter",
            "search_chapters",
            "update_index",
        ),
        "summary_read": (
            "read_chapter_summaries",
            "read_range_summaries",
        ),
        "character_read": ("list_characters", "read_character"),
        "character_write": (
            "create_character",
            "edit_character",
            "delete_character",
        ),
        "world_read": ("list_world_entries", "read_world_entry"),
        "world_write": (
            "create_world_entry",
            "edit_world_entry",
            "delete_world_entry",
        ),
        "note_read": (
            "list_notes",
            "read_note",
        ),
        "note_write": (
            "write_note",
            "edit_note",
            "delete_note",
            "move_note",
            "create_note_category",
            "edit_note_category",
            "delete_note_category",
        ),
        "chapter_write": (
            "write_chapter",
            "edit_chapter",
            "delete_chapter",
            "create_volume",
            "edit_volume",
            "delete_volume",
            "move_chapter_to_volume",
        ),
    }
)

TOOL_CATEGORY_DISPLAY: Mapping[str, str] = MappingProxyType(
    {
        "orchestration": "Delegasi Subtugas",
        "interaction": "Bertanya",
        "web_search": "Pencarian Web",
        "web_fetch": "Baca Halaman Web",
        "plan": "Rencana",
        "chapter_read": "Baca Bab",
        "summary_read": "Baca Ringkasan",
        "character_read": "Baca Tokoh",
        "character_write": "Tulis Tokoh",
        "world_read": "Baca Buku Dunia",
        "world_write": "Tulis Buku Dunia",
        "note_read": "Baca Catatan",
        "note_write": "Tulis Catatan",
        "chapter_write": "Tulis Bab",
    }
)


def list_tool_categories() -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    return tuple(
        (
            key,
            TOOL_CATEGORY_DISPLAY.get(key, key),
            TOOL_CATEGORIES[key],
        )
        for key in TOOL_CATEGORIES
    )


def get_tool_names_for_categories(category_keys: Iterable[str]) -> tuple[str, ...]:
    """Expand category keys to an ordered, de-duplicated tool-name tuple."""
    names: list[str] = []
    seen: set[str] = set()
    for category_key in category_keys:
        for tool_name in TOOL_CATEGORIES[category_key]:
            if tool_name in LOCAL_ONLY_TOOL_NAMES:
                continue
            if tool_name in seen:
                continue
            names.append(tool_name)
            seen.add(tool_name)
    return tuple(names)
