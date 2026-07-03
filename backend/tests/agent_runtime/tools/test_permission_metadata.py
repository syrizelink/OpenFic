from app.agent_runtime.tools.permission_metadata import (
    SETTING_KEY_AGENT_TOOL_PERMISSIONS,
    get_default_agent_tool_permissions,
    get_default_tool_permission_mode,
    resolve_tool_permission_key,
)


def test_runtime_tool_permissions_match_registered_user_tools() -> None:
    assert SETTING_KEY_AGENT_TOOL_PERMISSIONS == "agent_tool_permissions"
    assert get_default_agent_tool_permissions() == [
        {"tool_name": "ask_user", "mode": "allow"},
        {"tool_name": "create_plan", "mode": "ask"},
        {"tool_name": "create_volume", "mode": "ask"},
        {"tool_name": "create_world_entry", "mode": "ask"},
        {"tool_name": "delete_chapter", "mode": "ask"},
        {"tool_name": "delete_volume", "mode": "ask"},
        {"tool_name": "delete_world_entry", "mode": "ask"},
        {"tool_name": "edit_chapter", "mode": "ask"},
        {"tool_name": "edit_volume", "mode": "ask"},
        {"tool_name": "edit_world_entry", "mode": "ask"},
        {"tool_name": "get_plan", "mode": "allow"},
        {"tool_name": "list_chapters", "mode": "allow"},
        {"tool_name": "list_plan", "mode": "allow"},
        {"tool_name": "list_volumes", "mode": "allow"},
        {"tool_name": "list_world_entries", "mode": "allow"},
        {"tool_name": "move_chapter_to_volume", "mode": "ask"},
        {"tool_name": "read_chapter", "mode": "allow"},
        {"tool_name": "read_chapter_summaries", "mode": "allow"},
        {"tool_name": "read_range_summaries", "mode": "allow"},
        {"tool_name": "read_world_entry", "mode": "allow"},
        {"tool_name": "search_chapters", "mode": "allow"},
        {"tool_name": "update_index", "mode": "allow"},
        {"tool_name": "update_plan", "mode": "ask"},
        {"tool_name": "write_chapter", "mode": "ask"},
    ]


def test_runtime_tool_permission_helpers_use_tool_names() -> None:
    assert resolve_tool_permission_key("ask_user") == "ask_user"
    assert resolve_tool_permission_key("get_plan") == "get_plan"
    assert resolve_tool_permission_key("unknown_tool") == "unknown_tool"
    assert get_default_tool_permission_mode("create_plan") == "ask"
    assert get_default_tool_permission_mode("search_chapters") == "allow"
    assert get_default_tool_permission_mode("write_chapter") == "ask"
    assert get_default_tool_permission_mode("unknown_tool") is None
