import json
from dataclasses import replace
from types import MappingProxyType, SimpleNamespace

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

    with pytest.raises(
        ToolExecutionError, match="not in the delegatable agents whitelist"
    ):
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
        await common.ensure_primary(
            {"active_agent": "disabled-primary"}, lambda: Session()
        )


@pytest.mark.asyncio
async def test_dispatch_subagent_returns_dispatch_id_when_child_request_is_cancelled(
    monkeypatch: pytest.MonkeyPatch,
):
    import app.agent_runtime.tools.impls.orchestration.dispatch_subagent as dispatch_module

    row = SimpleNamespace(
        id="child-run-1",
        child_thread_id="parent:child:dispatch-cancelled",
        dispatch_id="dispatch-cancelled",
        metadata_json={"agent_number": 3},
        pending_approval_json=None,
    )

    async def noop(*_args, **_kwargs) -> None:
        return None

    async def open_session(*_args, **_kwargs) -> object:
        return object()

    async def load_waiting_child_run(*_args, **_kwargs):
        return None

    async def create_child_run(*_args, **_kwargs):
        return row

    async def persist_child_user_message(*_args, **_kwargs):
        return SimpleNamespace(id="message-1", seq=1)

    async def load_initial_request_id(*_args, **_kwargs) -> str:
        return "request-1"

    async def wait_for_assistant_content(*_args, **_kwargs) -> str:
        raise ToolExecutionError("subagent request was cancelled")

    class Runner:
        async def publish_parent_subagent_status(self, _child_run_id: str) -> None:
            return None

    monkeypatch.setattr(DispatchSubagentTool, "_validate_dispatch", noop)
    monkeypatch.setattr(
        DispatchSubagentTool,
        "_load_waiting_child_run",
        load_waiting_child_run,
    )
    monkeypatch.setattr(DispatchSubagentTool, "_create_child_run", create_child_run)
    monkeypatch.setattr(
        DispatchSubagentTool,
        "_load_initial_request_id",
        load_initial_request_id,
    )
    monkeypatch.setattr(
        DispatchSubagentTool,
        "_wait_for_assistant_content",
        wait_for_assistant_content,
    )
    monkeypatch.setattr(dispatch_module, "latest_checkpoint_id_for_thread", noop)
    monkeypatch.setattr(
        dispatch_module, "persist_child_user_message", persist_child_user_message
    )
    monkeypatch.setattr(dispatch_module, "open_session", open_session)
    monkeypatch.setattr(dispatch_module, "close_session", noop)
    monkeypatch.setattr(dispatch_module, "update_child_run_request_boundaries", noop)
    monkeypatch.setattr(
        dispatch_module, "make_subagent_runner", lambda **_kwargs: Runner()
    )

    tool = DispatchSubagentTool(
        _state={
            "session_id": "parent",
            "task_id": "task-1",
            "project_id": "project-1",
        }
    )

    result = json.loads(
        await tool._arun(
            agent_type="writer",
            description="write scene",
            prompt="write scene",
        )
    )

    assert result == {
        "dispatch_id": "dispatch-cancelled",
        "agent_number": 3,
        "error": "subagent request was cancelled",
    }
