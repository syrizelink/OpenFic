"""Tool category registry for PA/SA agent definitions."""

from collections.abc import Iterable, Mapping
from types import MappingProxyType

TOOL_CATEGORIES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "orchestration": (
            "dispatch_subagent",
            "notify_subagent",
            "recycle_subagent",
        ),
        "interaction": ("ask_user",),
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
        "orchestration": "委派子任务",
        "interaction": "提问",
        "plan": "计划",
        "chapter_read": "章节读取",
        "summary_read": "摘要读取",
        "character_read": "角色读取",
        "character_write": "角色写入",
        "world_read": "世界书读取",
        "world_write": "世界书写入",
        "note_read": "笔记读取",
        "note_write": "笔记写入",
        "chapter_write": "章节写入",
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
            if tool_name in seen:
                continue
            names.append(tool_name)
            seen.add(tool_name)
    return tuple(names)
