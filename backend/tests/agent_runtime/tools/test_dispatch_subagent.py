from dataclasses import replace
from types import MappingProxyType

import pytest

from app.agent_runtime.agents.definitions import AgentDefinition
from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls.orchestration import common
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
        "build": _make_definition("build", "primary"),
        "explore": _make_definition("explore", "subagent"),
    }

    async def load_definition(
        _self: DispatchSubagentTool,
        agent_key: str,
        _configurable: dict,
    ) -> AgentDefinition:
        return definitions[agent_key]

    monkeypatch.setattr(DispatchSubagentTool, "_load_definition", load_definition)
    tool = DispatchSubagentTool(_state={"active_agent": "build"})

    with pytest.raises(ToolExecutionError, match="not in the delegatable agents whitelist"):
        await tool._validate_dispatch("explore", {})


@pytest.mark.asyncio
async def test_ensure_primary_accepts_custom_primary_agent(
    monkeypatch: pytest.MonkeyPatch,
):
    class Session:
        async def close(self) -> None:
            pass

    async def load_definition(
        _session: Session,
        agent_key: str,
    ) -> AgentDefinition:
        assert agent_key == "custom-primary"
        return _make_definition("custom-primary", "primary")

    monkeypatch.setattr(common, "load_agent_definition", load_definition)

    await common.ensure_primary({"active_agent": "custom-primary"}, lambda: Session())


@pytest.mark.asyncio
async def test_ensure_primary_rejects_subagent(
    monkeypatch: pytest.MonkeyPatch,
):
    class Session:
        async def close(self) -> None:
            pass

    async def load_definition(
        _session: Session,
        _agent_key: str,
    ) -> AgentDefinition:
        return _make_definition("writer", "subagent")

    monkeypatch.setattr(common, "load_agent_definition", load_definition)

    with pytest.raises(ToolExecutionError, match="primary agent"):
        await common.ensure_primary({"active_agent": "writer"}, lambda: Session())


@pytest.mark.asyncio
async def test_ensure_primary_rejects_disabled_primary_agent(
    monkeypatch: pytest.MonkeyPatch,
):
    class Session:
        async def close(self) -> None:
            pass

    async def load_definition(
        _session: Session,
        _agent_key: str,
    ) -> AgentDefinition:
        definition = _make_definition("disabled-primary", "primary")
        return replace(definition, enabled=False)

    monkeypatch.setattr(common, "load_agent_definition", load_definition)

    with pytest.raises(ToolExecutionError, match="primary agent"):
        await common.ensure_primary({"active_agent": "disabled-primary"}, lambda: Session())
