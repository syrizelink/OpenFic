import json
from types import SimpleNamespace

import pytest

from app.agent_runtime.tools.impls.orchestration.recycle_subagent import (
    RecycleSubagentTool,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("is_active", [True, False])
async def test_recycle_subagent_returns_subagent_identity(
    monkeypatch: pytest.MonkeyPatch,
    is_active: bool,
) -> None:
    import app.agent_runtime.tools.impls.orchestration.recycle_subagent as recycle_module

    row = SimpleNamespace(
        id="child-run-1",
        dispatch_id="dispatch-writer",
        agent_key="writer",
        metadata_json={"agent_number": "#1001"},
        is_active=is_active,
    )

    async def noop(*_args, **_kwargs) -> None:
        return None

    async def resolve_child_run(*_args, **_kwargs):
        return row

    async def open_session(*_args, **_kwargs) -> object:
        return object()

    async def recycle_child_run(*_args, **_kwargs):
        return row

    class Registry:
        async def cancel_child(self, *_args, **_kwargs) -> None:
            return None

    class Runner:
        async def publish_parent_subagent_status(self, *_args, **_kwargs) -> None:
            return None

    monkeypatch.setattr(recycle_module, "ensure_primary", noop)
    monkeypatch.setattr(recycle_module, "resolve_child_run", resolve_child_run)
    monkeypatch.setattr(recycle_module, "open_session", open_session)
    monkeypatch.setattr(recycle_module, "close_session", noop)
    monkeypatch.setattr(recycle_module, "recycle_child_run", recycle_child_run)
    monkeypatch.setattr(recycle_module, "get_agent_run_registry", lambda: Registry())
    monkeypatch.setattr(
        recycle_module, "make_subagent_runner", lambda **_kwargs: Runner()
    )
    tool = RecycleSubagentTool(
        _state={
            "session_id": "parent",
            "project_id": "project-1",
            "active_agent": "primary",
        }
    )

    result = json.loads(
        await tool._execute(dispatch_id="dispatch-writer", reason="任务完成")
    )

    assert result == {
        "dispatch_id": "dispatch-writer",
        "agent_key": "writer",
        "agent_number": "#1001",
        "metadata": {"agent_number": "#1001"},
        "recycled": True,
    }
