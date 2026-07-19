from __future__ import annotations

from collections.abc import Mapping

from app.agent_runtime.agents.definitions import AgentDefinition
from app.agent_runtime.tools.base import AgentTool, ToolBuildHook


def _build_delegatable_subagent_lines(
    *,
    agent_definitions: Mapping[str, AgentDefinition],
    primary_agent_key: str,
) -> list[str]:
    primary_definition = agent_definitions.get(primary_agent_key)
    if primary_definition is None or primary_definition.kind != "primary":
        return []

    delegatable = set(primary_definition.delegatable_agents)
    lines: list[str] = []
    for agent_key, definition in agent_definitions.items():
        if agent_key == primary_agent_key:
            continue
        if definition.kind != "subagent" or not definition.enabled:
            continue
        if delegatable and agent_key not in delegatable:
            continue
        description = definition.description.strip() or "未提供职责描述。"
        lines.append(f"- {agent_key}：{description}")
    return lines


def build_dispatch_subagent_description_hook(
    *,
    agent_definitions: Mapping[str, AgentDefinition],
    primary_agent_key: str,
) -> ToolBuildHook:
    lines = _build_delegatable_subagent_lines(
        agent_definitions=agent_definitions,
        primary_agent_key=primary_agent_key,
    )

    def hook(tool: AgentTool) -> None:
        if tool.name != "dispatch_subagent" or not lines:
            return
        suffix = "当前可委派的 agent（使用`agent_type`指定）：\n" + "\n".join(lines)
        tool.description = f"{tool.description.rstrip()}\n\n{suffix}"

    return hook
