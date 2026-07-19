from types import MappingProxyType

import pytest

from app.agent_runtime.agents.definitions import AgentDefinition
from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls.orchestration.dispatch_subagent import (
    DispatchSubagentTool,
)


def _make_definition(
    key: str,
    kind: str,
    delegatable_agents: tuple[str, ...] = (),
) -> AgentDefinition:
    return AgentDefinition(
        key=key,
        display_name=key,
        description=key,
        kind=kind,  # type: ignore[arg-type]
        prompt_agent_name=key,
        model_id=None,
        enabled_tool_categories=(),
        enabled_skills=(),
        metadata=MappingProxyType({}),
        delegatable_agents=delegatable_agents,
    )


@pytest.mark.asyncio
async def test_dispatch_subagent_rejects_empty_primary_delegatable_agents(
    monkeypatch: pytest.MonkeyPatch,
):
    definitions = {
        "primary": _make_definition("primary", "primary"),
        "explorer": _make_definition("explorer", "subagent"),
    }

    async def load_definition(
        _self: DispatchSubagentTool,
        agent_key: str,
        _configurable: dict,
    ) -> AgentDefinition:
        return definitions[agent_key]

    monkeypatch.setattr(DispatchSubagentTool, "_load_definition", load_definition)
    tool = DispatchSubagentTool(_state={"active_agent": "primary"})

    with pytest.raises(ToolExecutionError, match="not in the delegatable agents whitelist"):
        await tool._validate_dispatch("explorer", {})
