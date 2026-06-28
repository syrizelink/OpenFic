import asyncio
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient

from app.agent_runtime.context.compaction.service import CompactionError
from app.api.routers.agent_runtime import _SESSION_RUNNERS


@pytest.fixture(autouse=True)
def reset_agent_runtime_runners():
    _SESSION_RUNNERS.clear()
    try:
        yield
    finally:
        _SESSION_RUNNERS.clear()


def _runner(
    *,
    compact_result: dict | None = None,
    compact_error: Exception | None = None,
    pending: tuple[str, str] | None = None,
):
    runner = SimpleNamespace(
        session_id="sess_compaction_api",
        task_id="task_compaction_api",
        project_id="proj_compaction_api",
        peek_next_pending_user_message=MagicMock(return_value=pending),
        consume_next_pending_user_message_for_continuation=AsyncMock(
            return_value=pending
        ),
        run=MagicMock(return_value=object()),
    )
    if compact_error is not None:
        runner.compact = AsyncMock(side_effect=compact_error)
    else:
        runner.compact = AsyncMock(
            return_value=compact_result
            or {
                "compaction_id": "cmp_api_1",
                "start_seq": 2,
                "end_seq": 7,
                "source_input_tokens": 1234,
                "summary_tokens": 98,
            }
        )
    return runner


def _registry(*, running: bool = False):
    return SimpleNamespace(
        is_running=AsyncMock(return_value=running),
        try_register_parent=AsyncMock(return_value=not running),
        register=AsyncMock(),
        unregister=AsyncMock(return_value=True),
        cancel=AsyncMock(),
    )


def _message_runner(*, can_continue: bool = False):
    return SimpleNamespace(
        session_id="sess_compaction_api",
        task_id="task_compaction_api",
        project_id="proj_compaction_api",
        can_continue=AsyncMock(return_value=can_continue),
        continue_with_user_message=MagicMock(return_value=object()),
        queue_pending_user_message=AsyncMock(
            return_value={
                "message_id": "msg_pending_1",
                "content": "压缩期间追加需求",
                "created_at": "2026-06-12T00:00:00+00:00",
            }
        ),
        run=MagicMock(return_value=object()),
    )


@pytest.mark.asyncio
async def test_manual_compaction_returns_structured_metrics(client: AsyncClient) -> None:
    runner = _runner()
    registry = _registry()

    with patch(
        "app.api.routers.agent_runtime._get_runner",
        AsyncMock(return_value=runner),
    ), patch(
        "app.api.routers.agent_runtime.get_agent_run_registry",
        return_value=registry,
    ), patch(
        "app.api.routers.agent_runtime._set_task_running_state",
        AsyncMock(),
    ) as set_running, patch(
        "app.api.routers.agent_runtime._launch_task",
        AsyncMock(),
    ) as launch_task:
        response = await client.post(
            "/api/v1/agent/sessions/sess_compaction_api/compaction"
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "success": True,
        "session_id": "sess_compaction_api",
        "compaction_id": "cmp_api_1",
        "start_seq": 2,
        "end_seq": 7,
        "source_input_tokens": 1234,
        "summary_tokens": 98,
    }
    runner.compact.assert_awaited_once_with()
    runner.consume_next_pending_user_message_for_continuation.assert_awaited_once_with()
    runner.peek_next_pending_user_message.assert_not_called()
    launch_task.assert_not_awaited()
    assert set_running.await_count == 2


@pytest.mark.asyncio
async def test_manual_compaction_rejects_while_session_is_running(
    client: AsyncClient,
) -> None:
    runner = _runner()
    registry = _registry(running=True)

    with patch(
        "app.api.routers.agent_runtime._get_runner",
        AsyncMock(return_value=runner),
    ), patch(
        "app.api.routers.agent_runtime.get_agent_run_registry",
        return_value=registry,
    ), patch(
        "app.api.routers.agent_runtime._set_task_running_state",
        AsyncMock(),
    ) as set_running:
        response = await client.post(
            "/api/v1/agent/sessions/sess_compaction_api/compaction"
        )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == {
        "code": "session_compacting",
        "message": "会话运行中，不能手动压缩",
    }
    runner.compact.assert_not_awaited()
    registry.try_register_parent.assert_not_awaited()
    set_running.assert_not_awaited()


@pytest.mark.asyncio
async def test_manual_compaction_maps_no_window_error_to_conflict(
    client: AsyncClient,
) -> None:
    runner = _runner(
        compact_error=CompactionError(
            "no_compactable_window",
            "没有可压缩的上下文窗口",
        )
    )
    registry = _registry()

    with patch(
        "app.api.routers.agent_runtime._get_runner",
        AsyncMock(return_value=runner),
    ), patch(
        "app.api.routers.agent_runtime.get_agent_run_registry",
        return_value=registry,
    ), patch(
        "app.api.routers.agent_runtime._set_task_running_state",
        AsyncMock(),
    ), patch(
        "app.api.routers.agent_runtime._launch_task",
        AsyncMock(),
    ) as launch_task:
        response = await client.post(
            "/api/v1/agent/sessions/sess_compaction_api/compaction"
        )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == {
        "code": "no_compactable_window",
        "message": "没有可压缩的上下文窗口",
    }
    launch_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_manual_compaction_maps_empty_summary_error_to_conflict(
    client: AsyncClient,
) -> None:
    runner = _runner(
        compact_error=CompactionError(
            "compaction_empty_summary",
            "压缩结果为空",
        ),
        pending=("msg_pending_1", "压缩后继续处理"),
    )
    registry = _registry()

    with patch(
        "app.api.routers.agent_runtime._get_runner",
        AsyncMock(return_value=runner),
    ), patch(
        "app.api.routers.agent_runtime.get_agent_run_registry",
        return_value=registry,
    ), patch(
        "app.api.routers.agent_runtime._set_task_running_state",
        AsyncMock(),
    ), patch(
        "app.api.routers.agent_runtime._launch_task",
        AsyncMock(),
    ) as launch_task:
        response = await client.post(
            "/api/v1/agent/sessions/sess_compaction_api/compaction"
        )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == {
        "code": "compaction_empty_summary",
        "message": "压缩结果为空",
    }
    runner.consume_next_pending_user_message_for_continuation.assert_not_awaited()
    runner.peek_next_pending_user_message.assert_not_called()
    runner.run.assert_not_called()
    launch_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_manual_compaction_success_launches_pending_message_continuation(
    client: AsyncClient,
) -> None:
    runner = _runner(pending=("msg_pending_1", "压缩后继续处理"))
    continuation_coro = object()
    runner.run = MagicMock(return_value=continuation_coro)
    registry = _registry()
    events: list[str] = []

    async def unregister(session_id: str, task) -> bool:
        del session_id, task
        events.append("unregister_manual")
        return False

    async def launch_continuation(**kwargs) -> None:
        assert kwargs["coro"] is continuation_coro
        events.append("launch_continuation")

    async def set_running_state(**kwargs) -> None:
        if kwargs["is_running"] is False:
            events.append("running_false")

    registry.unregister = AsyncMock(side_effect=unregister)

    with patch(
        "app.api.routers.agent_runtime._get_runner",
        AsyncMock(return_value=runner),
    ), patch(
        "app.api.routers.agent_runtime.get_agent_run_registry",
        return_value=registry,
    ), patch(
        "app.api.routers.agent_runtime._set_task_running_state",
        AsyncMock(side_effect=set_running_state),
    ), patch(
        "app.api.routers.agent_runtime._launch_continuation_task_replacing_current",
        AsyncMock(side_effect=launch_continuation),
        create=True,
    ) as launch_continuation_task:
        response = await client.post(
            "/api/v1/agent/sessions/sess_compaction_api/compaction"
        )

    assert response.status_code == status.HTTP_200_OK
    runner.consume_next_pending_user_message_for_continuation.assert_awaited_once_with()
    runner.peek_next_pending_user_message.assert_not_called()
    runner.run.assert_called_once_with(
        user_request="压缩后继续处理",
        user_message_id="msg_pending_1",
    )
    launch_continuation_task.assert_awaited_once()
    assert events == ["launch_continuation", "unregister_manual"]
    assert "running_false" not in events


@pytest.mark.asyncio
async def test_launch_continuation_replaces_current_registry_slot_without_gap() -> None:
    from app.api.routers.agent_runtime import (
        _launch_continuation_task_replacing_current,
    )

    session_id = "sess_compaction_api"
    current_task = cast(Any, object())
    continuation_task = cast(Any, object())
    registry = SimpleNamespace(
        _lock=asyncio.Lock(),
        _tasks={session_id: {"__parent__": current_task}},
        _cancelled_sessions=set(),
    )

    class _AwaitableProbe:
        def __await__(self):
            if False:
                yield None
            return None

    def create_task(coro):
        coro.close()
        return continuation_task

    with patch(
        "app.api.routers.agent_runtime.asyncio.create_task",
        MagicMock(side_effect=create_task),
    ), patch(
        "app.api.routers.agent_runtime._set_task_running_state",
        AsyncMock(),
    ):
        await _launch_continuation_task_replacing_current(
            db_session_factory=MagicMock(),
            session_id=session_id,
            task_id="task_compaction_api",
            project_id="proj_compaction_api",
            registry=registry,
            current_task=current_task,
            coro=_AwaitableProbe(),
        )

    assert registry._tasks[session_id]["__parent__"] is continuation_task


@pytest.mark.asyncio
async def test_send_message_queues_when_manual_compaction_running_even_if_interrupted(
    client: AsyncClient,
) -> None:
    runner = _message_runner(can_continue=True)
    registry = _registry(running=True)

    with patch(
        "app.api.routers.agent_runtime._get_runner",
        AsyncMock(return_value=runner),
    ), patch(
        "app.api.routers.agent_runtime.get_agent_run_registry",
        return_value=registry,
    ), patch(
        "app.api.routers.agent_runtime.task_service.get_task",
        AsyncMock(return_value=SimpleNamespace(title="Existing Task")),
    ), patch(
        "app.api.routers.agent_runtime._launch_task",
        AsyncMock(),
    ) as launch_task:
        response = await client.post(
            "/api/v1/agent/sessions/sess_compaction_api/message",
            json={"message": "压缩期间追加需求"},
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["success"] is True
    assert response.json()["queued"] is True
    assert response.json()["pending_message"] == {
        "message_id": "msg_pending_1",
        "content": "压缩期间追加需求",
        "created_at": "2026-06-12T00:00:00+00:00",
    }
    registry.is_running.assert_awaited_once_with("sess_compaction_api")
    runner.queue_pending_user_message.assert_awaited_once_with("压缩期间追加需求")
    runner.can_continue.assert_not_awaited()
    runner.continue_with_user_message.assert_not_called()
    runner.run.assert_not_called()
    launch_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_message_continues_interrupted_session_when_not_running(
    client: AsyncClient,
) -> None:
    runner = _message_runner(can_continue=True)
    registry = _registry(running=False)

    with patch(
        "app.api.routers.agent_runtime._get_runner",
        AsyncMock(return_value=runner),
    ), patch(
        "app.api.routers.agent_runtime.get_agent_run_registry",
        return_value=registry,
    ), patch(
        "app.api.routers.agent_runtime.task_service.get_task",
        AsyncMock(return_value=SimpleNamespace(title="Existing Task")),
    ), patch(
        "app.api.routers.agent_runtime._launch_task",
        AsyncMock(),
    ) as launch_task:
        response = await client.post(
            "/api/v1/agent/sessions/sess_compaction_api/message",
            json={"message": "继续被中断的会话"},
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["success"] is True
    assert response.json()["queued"] is False
    registry.is_running.assert_awaited_once_with("sess_compaction_api")
    runner.can_continue.assert_awaited_once_with()
    runner.continue_with_user_message.assert_called_once_with("继续被中断的会话")
    runner.queue_pending_user_message.assert_not_awaited()
    runner.run.assert_not_called()
    launch_task.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_message_queues_ordinary_running_session(
    client: AsyncClient,
) -> None:
    runner = _message_runner(can_continue=False)
    registry = _registry(running=True)

    with patch(
        "app.api.routers.agent_runtime._get_runner",
        AsyncMock(return_value=runner),
    ), patch(
        "app.api.routers.agent_runtime.get_agent_run_registry",
        return_value=registry,
    ), patch(
        "app.api.routers.agent_runtime.task_service.get_task",
        AsyncMock(return_value=SimpleNamespace(title="Existing Task")),
    ), patch(
        "app.api.routers.agent_runtime._launch_task",
        AsyncMock(),
    ) as launch_task:
        response = await client.post(
            "/api/v1/agent/sessions/sess_compaction_api/message",
            json={"message": "运行中追加需求"},
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["success"] is True
    assert response.json()["queued"] is True
    registry.is_running.assert_awaited_once_with("sess_compaction_api")
    runner.queue_pending_user_message.assert_awaited_once_with("运行中追加需求")
    runner.can_continue.assert_not_awaited()
    runner.continue_with_user_message.assert_not_called()
    runner.run.assert_not_called()
    launch_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_launch_continuation_rejects_when_current_task_cannot_be_replaced() -> None:
    from app.api.routers.agent_runtime import (
        _launch_continuation_task_replacing_current,
    )

    continuation_task = MagicMock()
    registry = SimpleNamespace(register=AsyncMock())

    class _AwaitableProbe:
        def __await__(self):
            if False:
                yield None
            return None

    def create_task(coro):
        coro.close()
        return continuation_task

    with patch(
        "app.api.routers.agent_runtime.asyncio.create_task",
        MagicMock(side_effect=create_task),
    ):
        with pytest.raises(RuntimeError, match="replace current agent task"):
            await _launch_continuation_task_replacing_current(
                db_session_factory=MagicMock(),
                session_id="sess_compaction_api",
                task_id="task_compaction_api",
                project_id="proj_compaction_api",
                registry=registry,
                current_task=cast(Any, object()),
                coro=_AwaitableProbe(),
            )

    continuation_task.cancel.assert_called_once_with()
    registry.register.assert_not_awaited()


@pytest.mark.asyncio
async def test_rollback_rejects_running_session_without_cancelling(
    client: AsyncClient,
) -> None:
    fake_runner = SimpleNamespace(cancel=MagicMock())
    _SESSION_RUNNERS["sess_compaction_api"] = cast(Any, fake_runner)
    registry = _registry(running=True)
    rollback_result = SimpleNamespace(
        restored_checkpoint_id=None,
        rollback_revision=SimpleNamespace(id="rev_rollback_unexpected"),
        affected_chapters=[],
        restored_message_content="",
    )

    with patch(
        "app.api.routers.agent_runtime.get_agent_run_registry",
        return_value=registry,
    ), patch(
        "app.api.routers.agent_runtime.rollback_revision_for_session",
        AsyncMock(return_value=rollback_result),
    ) as rollback_revision:
        response = await client.post(
            "/api/v1/agent/sessions/sess_compaction_api/rollback",
            json={"revision_id": "rev_before_compaction"},
        )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == "会话运行中，不能回滚"
    fake_runner.cancel.assert_not_called()
    registry.cancel.assert_not_awaited()
    rollback_revision.assert_not_awaited()
