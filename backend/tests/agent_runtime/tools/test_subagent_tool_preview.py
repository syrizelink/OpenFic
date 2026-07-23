from types import SimpleNamespace

import pytest

from app.agent_runtime.tools.errors import ToolExecutionError
from app.agent_runtime.tools.impls.orchestration import common
from app.agent_runtime.tools.impls.orchestration.dispatch_subagent import (
    DispatchSubagentTool,
)
from app.agent_runtime.tools.impls.orchestration.notify_subagent import (
    NotifySubagentTool,
)


@pytest.mark.asyncio
async def test_subagent_tool_preview_emits_identity_for_running_tool() -> None:
    emitted: list[tuple[str, dict]] = []
    row = SimpleNamespace(
        dispatch_id="dispatch-writer",
        agent_key="writer",
        metadata_json={"agent_number": "#1001"},
    )

    async def event_sink(name: str, payload: dict) -> None:
        emitted.append((name, payload))

    emit_preview = getattr(common, "emit_subagent_tool_preview", None)

    assert callable(emit_preview)
    await emit_preview(
        configurable={"agent_event_sink": event_sink},
        parent_session_id="parent-session",
        tool_call_id="call-dispatch",
        tool_name="dispatch_subagent",
        tool_args={"agent_type": "writer", "prompt": "写场景"},
        row=row,
    )

    assert emitted == [
        (
            "agent:tool_result",
            {
                "session_id": "parent-session",
                "tool_call_id": "call-dispatch",
                "tool": "dispatch_subagent",
                "input": {"agent_type": "writer", "prompt": "写场景"},
                "output": {
                    "type": "preview",
                    "success": True,
                    "dispatch_id": "dispatch-writer",
                    "agent_key": "writer",
                    "agent_number": "#1001",
                    "metadata": {"agent_number": "#1001"},
                },
                "is_preview": True,
            },
        )
    ]


@pytest.mark.asyncio
async def test_dispatch_subagent_emits_preview_after_child_run_is_created(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.agent_runtime.tools.impls.orchestration.dispatch_subagent as dispatch_module

    row = SimpleNamespace(
        id="child-run-1",
        child_thread_id="parent:child:dispatch-writer",
        dispatch_id="dispatch-writer",
        agent_key="writer",
        metadata_json={"agent_number": "#1001"},
        pending_approval_json=None,
    )
    previews: list[dict] = []

    async def noop(*_args, **_kwargs) -> None:
        return None

    async def open_session(*_args, **_kwargs) -> object:
        return object()

    async def create_child_run(*_args, **_kwargs):
        return row

    async def load_initial_request_id(*_args, **_kwargs) -> str:
        return "request-1"

    async def persist_child_user_message(*_args, **_kwargs):
        return SimpleNamespace(id="message-1", seq=1)

    async def wait_for_assistant_content(*_args, **_kwargs) -> str:
        raise ToolExecutionError("subagent request was cancelled")

    async def emit_preview(**kwargs) -> None:
        previews.append(kwargs)

    class Runner:
        async def publish_parent_subagent_status(self, _child_run_id: str) -> None:
            return None

    monkeypatch.setattr(DispatchSubagentTool, "_validate_dispatch", noop)
    monkeypatch.setattr(DispatchSubagentTool, "_load_waiting_child_run", noop)
    monkeypatch.setattr(DispatchSubagentTool, "_create_child_run", create_child_run)
    monkeypatch.setattr(
        DispatchSubagentTool, "_load_initial_request_id", load_initial_request_id
    )
    monkeypatch.setattr(
        DispatchSubagentTool,
        "_wait_for_assistant_content",
        wait_for_assistant_content,
    )
    monkeypatch.setattr(dispatch_module, "latest_checkpoint_id_for_thread", noop)
    monkeypatch.setattr(
        dispatch_module,
        "persist_child_user_message",
        persist_child_user_message,
    )
    monkeypatch.setattr(dispatch_module, "open_session", open_session)
    monkeypatch.setattr(dispatch_module, "close_session", noop)
    monkeypatch.setattr(dispatch_module, "update_child_run_request_boundaries", noop)
    monkeypatch.setattr(
        dispatch_module, "make_subagent_runner", lambda **_kwargs: Runner()
    )
    monkeypatch.setattr(
        dispatch_module,
        "emit_subagent_tool_preview",
        emit_preview,
        raising=False,
    )
    tool = DispatchSubagentTool(
        _state={
            "session_id": "parent",
            "task_id": "task-1",
            "project_id": "project-1",
        }
    )

    await tool._arun(
        agent_type="writer",
        description="写场景",
        prompt="请续写这一场景。",
        config={"metadata": {"tool_call_id": "call-dispatch"}},
    )

    assert previews == [
        {
            "configurable": {},
            "parent_session_id": "parent",
            "tool_call_id": "call-dispatch",
            "tool_name": "dispatch_subagent",
            "tool_args": {
                "agent_type": "writer",
                "description": "写场景",
                "prompt": "请续写这一场景。",
            },
            "row": row,
        }
    ]


@pytest.mark.asyncio
async def test_notify_subagent_emits_preview_after_request_is_queued(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.agent_runtime.tools.impls.orchestration.notify_subagent as notify_module

    row = SimpleNamespace(
        id="child-run-1",
        child_thread_id="parent:child:dispatch-writer",
        dispatch_id="dispatch-writer",
        agent_key="writer",
        metadata_json={"agent_number": "#1001"},
        pending_approval_json=None,
        is_active=True,
    )
    previews: list[dict] = []

    async def noop(*_args, **_kwargs) -> None:
        return None

    async def open_session(*_args, **_kwargs) -> object:
        return object()

    async def resolve_child_run(*_args, **_kwargs):
        return row

    async def enqueue_child_run_request(*_args, **_kwargs):
        return SimpleNamespace(id="request-1")

    async def persist_child_user_message(*_args, **_kwargs):
        return SimpleNamespace(id="message-1", seq=1)

    async def wait_for_assistant_content(*_args, **_kwargs) -> str:
        raise ToolExecutionError("subagent request was cancelled")

    async def emit_preview(**kwargs) -> None:
        previews.append(kwargs)

    class Runner:
        async def publish_parent_subagent_status(self, _child_run_id: str) -> None:
            return None

    monkeypatch.setattr(notify_module, "ensure_primary", noop)
    monkeypatch.setattr(notify_module, "resolve_child_run", resolve_child_run)
    monkeypatch.setattr(notify_module, "latest_checkpoint_id_for_thread", noop)
    monkeypatch.setattr(
        notify_module, "enqueue_child_run_request", enqueue_child_run_request
    )
    monkeypatch.setattr(
        notify_module,
        "persist_child_user_message",
        persist_child_user_message,
    )
    monkeypatch.setattr(notify_module, "open_session", open_session)
    monkeypatch.setattr(notify_module, "close_session", noop)
    monkeypatch.setattr(notify_module, "update_child_run_request_boundaries", noop)
    monkeypatch.setattr(
        notify_module, "make_subagent_runner", lambda **_kwargs: Runner()
    )
    monkeypatch.setattr(
        notify_module,
        "emit_subagent_tool_preview",
        emit_preview,
        raising=False,
    )
    monkeypatch.setattr(
        NotifySubagentTool,
        "_wait_for_assistant_content",
        wait_for_assistant_content,
    )
    tool = NotifySubagentTool(
        _state={
            "session_id": "parent",
            "task_id": "task-1",
            "project_id": "project-1",
        }
    )

    await tool._arun(
        dispatch_id="dispatch-writer",
        prompt="请继续完善冲突。",
        config={"metadata": {"tool_call_id": "call-notify"}},
    )

    assert previews == [
        {
            "configurable": {},
            "parent_session_id": "parent",
            "tool_call_id": "call-notify",
            "tool_name": "notify_subagent",
            "tool_args": {
                "dispatch_id": "dispatch-writer",
                "prompt": "请继续完善冲突。",
            },
            "row": row,
        }
    ]
