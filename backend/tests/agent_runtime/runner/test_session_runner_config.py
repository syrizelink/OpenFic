import asyncio
import weakref
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agent_runtime.context import ContextBuildError
from app.agent_runtime.runner.run_registry import AgentRunRegistry
from app.agent_runtime.runner.session_runner import SessionRunner
from app.agent_runtime.tools.impls.orchestration.common import ensure_child_processing


def test_missing_max_context_tokens_raises() -> None:
    with pytest.raises(ContextBuildError) as exc:
        SessionRunner(
            session_id="s1",
            task_id="task_test",
            model_config={},
            project_id="p1",
        )
    assert exc.value.part == "config"


def test_zero_max_context_tokens_disables_context_compaction() -> None:
    runner = SessionRunner(
        session_id="s1",
        task_id="task_test",
        model_config={"max_context_tokens": 0},
        project_id="p1",
    )

    assert runner.model_config["max_context_tokens"] == 0


def test_valid_config_constructs_ok() -> None:
    runner = SessionRunner(
        session_id="s1",
        task_id="task_test",
        model_config={"max_context_tokens": 8000},
        project_id="p1",
    )
    assert runner.session_id == "s1"


@pytest.mark.asyncio
async def test_register_can_preserve_session_cancellation() -> None:
    registry = AgentRunRegistry()
    blocker = asyncio.Event()
    task = asyncio.create_task(blocker.wait())
    try:
        await registry.mark_cancelled("session-cancelled")
        await registry.register("session-cancelled", task, clear_cancelled=False)

        assert await registry.is_cancelled("session-cancelled") is True
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_session_locks_are_not_retained_after_use() -> None:
    registry = AgentRunRegistry()
    lock = registry.session_lock("finished-session")
    lock_ref = weakref.ref(lock)

    del lock

    assert lock_ref() is None
    assert "finished-session" not in registry._session_locks


@pytest.mark.asyncio
async def test_child_resume_does_not_clear_session_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = AgentRunRegistry()
    monkeypatch.setattr(
        "app.agent_runtime.tools.impls.orchestration.common.get_agent_run_registry",
        lambda: registry,
    )
    await registry.mark_cancelled("session-cancelled")

    class Runner:
        called = False

        async def resume(self, child_run_id: str, payload: dict) -> None:
            self.called = True

    runner = Runner()
    started = await ensure_child_processing(
        parent_session_id="session-cancelled",
        child_run_id="child-1",
        runner=runner,
        resume_payload={"approved": True},
        clear_cancelled=False,
    )

    assert started is False
    assert runner.called is False
    assert await registry.is_cancelled("session-cancelled") is True
    assert await registry.is_child_running("session-cancelled", "child-1") is False


@pytest.mark.asyncio
async def test_losing_child_start_does_not_unregister_winner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = AgentRunRegistry()
    monkeypatch.setattr(
        "app.agent_runtime.tools.impls.orchestration.common.get_agent_run_registry",
        lambda: registry,
    )
    monkeypatch.setattr(
        "app.agent_runtime.tools.impls.orchestration.common._clear_child_processing_failure",
        AsyncMock(),
    )

    registrations_ready = asyncio.Event()
    registration_count = 0
    original_try_register_child = registry.try_register_child

    async def synchronized_try_register_child(
        session_id: str,
        child_run_id: str,
        task: asyncio.Task[None],
        *,
        clear_cancelled: bool = True,
    ) -> bool:
        nonlocal registration_count
        registration_count += 1
        if registration_count == 2:
            registrations_ready.set()
        await registrations_ready.wait()
        return await original_try_register_child(
            session_id,
            child_run_id,
            task,
            clear_cancelled=clear_cancelled,
        )

    monkeypatch.setattr(registry, "try_register_child", synchronized_try_register_child)

    runner_started = asyncio.Event()
    release_runner = asyncio.Event()

    class Runner:
        async def run(self, child_run_id: str) -> None:
            runner_started.set()
            await release_runner.wait()

    runner = Runner()
    results = await asyncio.gather(
        ensure_child_processing(
            parent_session_id="session-race",
            child_run_id="child-race",
            runner=runner,
        ),
        ensure_child_processing(
            parent_session_id="session-race",
            child_run_id="child-race",
            runner=runner,
        ),
    )

    await asyncio.wait_for(runner_started.wait(), timeout=1)
    assert sorted(results) == [False, True]
    assert await registry.is_child_running("session-race", "child-race") is True

    release_runner.set()
    for _ in range(10):
        if not await registry.is_child_running("session-race", "child-race"):
            break
        await asyncio.sleep(0)
    assert await registry.is_child_running("session-race", "child-race") is False


@pytest.mark.asyncio
async def test_child_completion_continuation_preserves_session_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.agent_runtime.runner.subagent_runner import SubagentRunner

    ensure = AsyncMock()
    monkeypatch.setattr(
        "app.agent_runtime.tools.impls.orchestration.common.ensure_child_processing",
        ensure,
    )
    runner = SubagentRunner(
        session_factory=None,
        model_config={},
        project_id="p1",
    )
    monkeypatch.setattr(
        runner,
        "_load_child_run",
        AsyncMock(
            return_value=SimpleNamespace(
                is_active=True,
                status="queued",
            )
        ),
    )
    monkeypatch.setattr(runner, "_count_pending_requests", AsyncMock(return_value=1))

    await runner.on_child_processing_finished(
        parent_session_id="session-cancelled",
        child_run_id="child-1",
    )

    assert ensure.await_args is not None
    assert ensure.await_args.kwargs["clear_cancelled"] is False
