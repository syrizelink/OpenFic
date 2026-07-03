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
    "ask_user": ToolPermissionMetadata(
        permission_key="ask_user",
        default_mode="allow",
    ),
    "get_plan": ToolPermissionMetadata(
        permission_key="get_plan",
        default_mode="allow",
    ),
    "list_plan": ToolPermissionMetadata(
        permission_key="list_plan",
        default_mode="allow",
    ),
    "create_plan": ToolPermissionMetadata(
        permission_key="create_plan",
        default_mode="ask",
    ),
    "update_plan": ToolPermissionMetadata(
        permission_key="update_plan",
        default_mode="ask",
    ),
    "read_chapter": ToolPermissionMetadata(
        permission_key="read_chapter",
        default_mode="allow",
    ),
    "search_chapters": ToolPermissionMetadata(
        permission_key="search_chapters",
        default_mode="allow",
    ),
    "update_index": ToolPermissionMetadata(
        permission_key="update_index",
        default_mode="allow",
    ),
    "list_chapters": ToolPermissionMetadata(
        permission_key="list_chapters",
        default_mode="allow",
    ),
    "list_volumes": ToolPermissionMetadata(
        permission_key="list_volumes",
        default_mode="allow",
    ),
    "read_chapter_summaries": ToolPermissionMetadata(
        permission_key="read_chapter_summaries",
        default_mode="allow",
    ),
    "read_range_summaries": ToolPermissionMetadata(
        permission_key="read_range_summaries",
        default_mode="allow",
    ),
    "list_world_entries": ToolPermissionMetadata(
        permission_key="list_world_entries",
        default_mode="allow",
    ),
    "read_world_entry": ToolPermissionMetadata(
        permission_key="read_world_entry",
        default_mode="allow",
    ),
    "create_world_entry": ToolPermissionMetadata(
        permission_key="create_world_entry",
        default_mode="ask",
    ),
    "edit_world_entry": ToolPermissionMetadata(
        permission_key="edit_world_entry",
        default_mode="ask",
    ),
    "delete_world_entry": ToolPermissionMetadata(
        permission_key="delete_world_entry",
        default_mode="ask",
    ),
    "write_chapter": ToolPermissionMetadata(
        permission_key="write_chapter",
        default_mode="ask",
    ),
    "edit_chapter": ToolPermissionMetadata(
        permission_key="edit_chapter",
        default_mode="ask",
    ),
    "delete_chapter": ToolPermissionMetadata(
        permission_key="delete_chapter",
        default_mode="ask",
    ),
    "create_volume": ToolPermissionMetadata(
        permission_key="create_volume",
        default_mode="ask",
    ),
    "edit_volume": ToolPermissionMetadata(
        permission_key="edit_volume",
        default_mode="ask",
    ),
    "delete_volume": ToolPermissionMetadata(
        permission_key="delete_volume",
        default_mode="ask",
    ),
    "move_chapter_to_volume": ToolPermissionMetadata(
        permission_key="move_chapter_to_volume",
        default_mode="ask",
    ),
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
