"""Permission metadata for agent_runtime tools."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolPermissionMetadata:
    """Permission configuration shared across settings and runtime."""

    permission_key: str
    default_mode: str


SETTING_KEY_AGENT_TOOL_PERMISSIONS = "agent_tool_permissions"
SETTING_KEY_AGENT_BYPASS_TOOL_APPROVAL = "agent_bypass_tool_approval"

_PERMISSION_METADATA_BY_TOOL_NAME = {
    "activate_skill": ToolPermissionMetadata("activate_skill", "allow"),
    "ask_user": ToolPermissionMetadata("ask_user", "allow"),
    "create_character": ToolPermissionMetadata("create_character", "ask"),
    "create_note_category": ToolPermissionMetadata("create_note_category", "ask"),
    "create_volume": ToolPermissionMetadata("create_volume", "ask"),
    "create_world_entry": ToolPermissionMetadata("create_world_entry", "ask"),
    "delete_chapter": ToolPermissionMetadata("delete_chapter", "ask"),
    "delete_character": ToolPermissionMetadata("delete_character", "ask"),
    "delete_note": ToolPermissionMetadata("delete_note", "ask"),
    "delete_note_category": ToolPermissionMetadata("delete_note_category", "ask"),
    "delete_volume": ToolPermissionMetadata("delete_volume", "ask"),
    "delete_world_entry": ToolPermissionMetadata("delete_world_entry", "ask"),
    "dispatch_subagent": ToolPermissionMetadata("dispatch_subagent", "allow"),
    "edit_chapter": ToolPermissionMetadata("edit_chapter", "ask"),
    "edit_character": ToolPermissionMetadata("edit_character", "ask"),
    "edit_note": ToolPermissionMetadata("edit_note", "ask"),
    "edit_note_category": ToolPermissionMetadata("edit_note_category", "ask"),
    "edit_volume": ToolPermissionMetadata("edit_volume", "ask"),
    "edit_world_entry": ToolPermissionMetadata("edit_world_entry", "ask"),
    "list_chapters": ToolPermissionMetadata("list_chapters", "allow"),
    "list_characters": ToolPermissionMetadata("list_characters", "allow"),
    "list_notes": ToolPermissionMetadata("list_notes", "allow"),
    "list_volumes": ToolPermissionMetadata("list_volumes", "allow"),
    "list_world_entries": ToolPermissionMetadata("list_world_entries", "allow"),
    "move_chapter_to_volume": ToolPermissionMetadata("move_chapter_to_volume", "ask"),
    "move_note": ToolPermissionMetadata("move_note", "ask"),
    "notify_subagent": ToolPermissionMetadata("notify_subagent", "allow"),
    "read_chapter": ToolPermissionMetadata("read_chapter", "allow"),
    "read_chapter_summaries": ToolPermissionMetadata("read_chapter_summaries", "allow"),
    "read_character": ToolPermissionMetadata("read_character", "allow"),
    "read_note": ToolPermissionMetadata("read_note", "allow"),
    "read_range_summaries": ToolPermissionMetadata("read_range_summaries", "allow"),
    "read_world_entry": ToolPermissionMetadata("read_world_entry", "allow"),
    "recycle_subagent": ToolPermissionMetadata("recycle_subagent", "allow"),
    "reference_skill": ToolPermissionMetadata("reference_skill", "allow"),
    "search_chapters": ToolPermissionMetadata("search_chapters", "allow"),
    "update_index": ToolPermissionMetadata("update_index", "allow"),
    "write_chapter": ToolPermissionMetadata("write_chapter", "ask"),
    "write_note": ToolPermissionMetadata("write_note", "ask"),
    "write_plan": ToolPermissionMetadata("write_plan", "ask"),
}


def get_tool_permission_metadata(tool_name: str) -> ToolPermissionMetadata | None:
    return _PERMISSION_METADATA_BY_TOOL_NAME.get(tool_name)


def resolve_tool_permission_key(tool_name: str) -> str:
    metadata = get_tool_permission_metadata(tool_name)
    if metadata is None:
        return tool_name
    return metadata.permission_key


def get_default_agent_tool_permissions() -> list[dict[str, str]]:
    items_by_key: dict[str, str] = {}
    for metadata in _PERMISSION_METADATA_BY_TOOL_NAME.values():
        items_by_key[metadata.permission_key] = metadata.default_mode

    return [
        {"tool_name": tool_name, "mode": mode}
        for tool_name, mode in sorted(items_by_key.items(), key=lambda item: item[0])
    ]


def get_default_tool_permission_mode(tool_name: str) -> str | None:
    metadata = get_tool_permission_metadata(tool_name)
    if metadata is None:
        return None
    return metadata.default_mode
