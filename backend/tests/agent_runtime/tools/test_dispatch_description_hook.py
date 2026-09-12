from types import MappingProxyType

from app.agent_runtime.agents.definitions import AgentDefinition, get_default_agent_definition
from app.agent_runtime.tools.registry import ToolRegistry
from app.agent_runtime.tools.hooks.dispatch_description import (
    build_dispatch_subagent_description_hook,
)


def _make_state() -> dict:
    return {
        "session_id": "s1",
        "project_id": "p1",
        "model_config": {},
        "active_agent": "primary",
        "is_completed": False,
        "error": None,
        "retry_count": 0,
        "message_checkpoints": [],
        "user_request": "",
    }


def test_dispatch_description_hook_appends_delegatable_agent_list():
    primary = AgentDefinition(
        key="primary",
        display_name="Orchestrator",
        description="primary",
        kind="primary",
        prompt_agent_name="orchestrator",
        model_id=None,
        enabled_tool_categories=("orchestration",),
        enabled_skills=(),
        metadata=MappingProxyType({}),
        delegatable_agents=("explore", "custom-bot"),
    )
    custom_bot = AgentDefinition(
        key="custom-bot",
        display_name="Custom Bot",
        description="Menangani tugas ekstensi kustom.",
        kind="subagent",
        prompt_agent_name="custom-bot",
        model_id=None,
        enabled_tool_categories=("chapter_read",),
        enabled_skills=(),
        metadata=MappingProxyType({}),
        source="custom",
    )
    agent_definitions = {
        "primary": primary,
        "explore": get_default_agent_definition("explore"),
        "writer": get_default_agent_definition("writer"),
        "custom-bot": custom_bot,
    }

    hook = build_dispatch_subagent_description_hook(
        agent_definitions=agent_definitions,
        primary_agent_key="primary",
    )
    tool = ToolRegistry.get_tools(
        names=["dispatch_subagent"],
        state=_make_state(),
        build_hooks=[hook],
    )[0]

    assert (
        "Agent yang dapat didelegasikan saat ini (tentukan dengan `agent_type`)"
        in tool.description
    )
    assert (
        "- explore: Menangani pengumpulan informasi, penataan konteks, dan pencarian bukti"
        in tool.description
    )
    assert "- custom-bot: Menangani tugas ekstensi kustom." in tool.description
    assert "- writer:" not in tool.description


def test_dispatch_description_hook_omits_agents_when_primary_has_no_delegatable_agents():
    primary = AgentDefinition(
        key="primary",
        display_name="Orchestrator",
        description="primary",
        kind="primary",
        prompt_agent_name="orchestrator",
        model_id=None,
        enabled_tool_categories=("orchestration",),
        enabled_skills=(),
        metadata=MappingProxyType({}),
    )
    hook = build_dispatch_subagent_description_hook(
        agent_definitions={
            "primary": primary,
            "explore": get_default_agent_definition("explore"),
        },
        primary_agent_key="primary",
    )
    tool = ToolRegistry.get_tools(
        names=["dispatch_subagent"],
        state=_make_state(),
        build_hooks=[hook],
    )[0]

    assert "Agent yang dapat didelegasikan saat ini" not in tool.description
