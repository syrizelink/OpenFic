from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage
from langgraph.errors import GraphRecursionError
from langgraph.types import Command

from app.agent_runtime.context.types import ContextMessage
from app.agent_runtime.runner.session_runner import SessionRunner


def test_session_runner_init():
    runner = SessionRunner(session_id="sess_001", task_id="task_001", model_config={
        "provider_type": "openai", "model_id": "gpt-4o", "api_key": "sk-test", "base_url": "",
        "max_context_tokens": 8000,
    })
    assert runner.session_id == "sess_001"
    assert not hasattr(runner, "mode")


def test_session_runner_inject_queue():
    runner = SessionRunner(session_id="sess_001", task_id="task_001", model_config={
        "provider_type": "openai", "model_id": "gpt-4o", "api_key": "sk-test", "base_url": "",
        "max_context_tokens": 8000,
    })
    assert runner._inject_queue is not None
    assert runner._inject_queue.empty()


def test_runtime_config_keeps_api_key_outside_persisted_state():
    runner = SessionRunner(
        session_id="sess_runtime_config",
        task_id="task_runtime_config",
        model_config={
            "model_record_id": "model-record-1",
            "provider_type": "openai-compatible",
            "model_id": "gpt-4o",
            "api_key": "sk-runtime",
            "base_url": "",
            "max_context_tokens": 8000,
        },
    )

    config = runner._build_runtime_config(
        runtime_session=MagicMock(),
        runtime_context={},
        audit_context=MagicMock(),
    )

    assert config["configurable"]["model_config"]["api_key"] == "sk-runtime"


@pytest.mark.asyncio
async def test_session_runner_inject_message():
    runner = SessionRunner(session_id="sess_001", task_id="task_001", model_config={
        "provider_type": "openai", "model_id": "gpt-4o", "api_key": "sk-test", "base_url": "",
        "max_context_tokens": 8000,
    })
    await runner.inject_message("user feedback", "msg_001")
    assert not runner._inject_queue.empty()
    msg = runner._inject_queue.get_nowait()
    assert msg == ("msg_001", "user", "user feedback")


@pytest.mark.asyncio
async def test_emit_user_message_includes_created_at():
    runner = SessionRunner(session_id="sess_001", task_id="task_001", model_config={
        "provider_type": "openai", "model_id": "gpt-4o", "api_key": "sk-test", "base_url": "",
        "max_context_tokens": 8000,
    })

    with patch("app.agent_runtime.runner.session_runner.emit", new=AsyncMock()) as emit_mock:
        await runner._emit_user_message("hello", "rev_001")

    payload = emit_mock.await_args.args[1]
    assert payload["content"] == "hello"
    assert payload["revision_id"] == "rev_001"
    assert isinstance(payload.get("created_at"), str) and payload["created_at"]


@pytest.mark.asyncio
async def test_run_emits_done_with_created_at():
    runner = SessionRunner(
        session_id="sess_done_001",
        task_id="task_done_001",
        model_config={
            "provider_type": "openai",
            "model_id": "gpt",
            "api_key": "k",
            "base_url": "",
            "max_context_tokens": 8000,
        },
    )

    class _Graph:
        async def astream_events(self, *args, **kwargs):
            if False:
                yield None

        async def aget_state(self, *args, **kwargs):
            return SimpleNamespace(next=(), tasks=(), values={}, config={"configurable": {}})

    fake_session = MagicMock(close=AsyncMock(), commit=AsyncMock())
    fake_persister = MagicMock(
        handle=AsyncMock(),
        mark_user_sent=AsyncMock(),
        finalize=AsyncMock(),
    )
    persisted_message = SimpleNamespace(
        id="msg_done_001",
        seq=0,
        created_at=datetime.now(UTC),
    )

    with patch.object(runner, "_get_graph", AsyncMock(return_value=_Graph())), \
         patch.object(runner, "_prepare_run_persistence", AsyncMock(return_value=[])), \
         patch.object(runner, "_persist_user_message", AsyncMock(return_value=persisted_message)), \
         patch(
             "app.agent_runtime.runner.session_runner.begin_user_revision",
             AsyncMock(return_value=SimpleNamespace(id="rev_done_001")),
         ), \
         patch("app.agent_runtime.runner.session_runner.finalize_revision_status", AsyncMock()), \
         patch("app.agent_runtime.runner.session_runner.emit", new=AsyncMock()) as emit_mock, \
         patch(
             "app.agent_runtime.runner.session_runner.create_session",
             AsyncMock(return_value=fake_session),
         ), \
         patch.object(runner, "_make_persister", MagicMock(return_value=fake_persister)):
        await runner.run(user_request="hi")

    done_payloads = [
        call.args[1]
        for call in emit_mock.await_args_list
        if call.args and call.args[0] == "agent:done"
    ]
    assert done_payloads
    assert isinstance(done_payloads[-1].get("created_at"), str) and done_payloads[-1]["created_at"]


@pytest.mark.asyncio
async def test_initial_state_does_not_include_context_anchor_state():
    runner = SessionRunner(
        session_id="sess_ctx_001",
        task_id="task_ctx_001",
        model_config={
            "provider_type": "openai",
            "model_id": "gpt",
            "api_key": "k",
            "base_url": "",
            "max_context_tokens": 8000,
        },
        project_id="proj_001",
    )
    captured: dict = {}
    captured_config: dict = {}

    class _Graph:
        async def astream_events(self, state, config, version):
            captured.update(state)
            captured_config.update(config)
            if False:
                yield None
        async def aget_state(self, config):
            class _S:
                next = ()
                tasks = ()
                values: dict = {}
            return _S()

    fake_session = MagicMock(close=AsyncMock(), commit=AsyncMock())
    begin_revision = AsyncMock(return_value=SimpleNamespace(id="rev_1"))
    with patch.object(runner, "_get_graph", AsyncMock(return_value=_Graph())), \
         patch.object(runner, "_prepare_run_persistence", AsyncMock(return_value=[])), \
         patch.object(runner, "_persist_user_message", AsyncMock(return_value=SimpleNamespace(id="msg_1", seq=0))), \
         patch("app.agent_runtime.runner.session_runner.begin_user_revision", begin_revision), \
         patch("app.agent_runtime.runner.session_runner.finalize_revision_status", AsyncMock()), \
         patch("app.agent_runtime.runner.session_runner.emit", AsyncMock()), \
         patch(
             "app.agent_runtime.runner.session_runner.create_session",
             AsyncMock(return_value=fake_session),
         ), \
         patch.object(runner, "_make_persister", MagicMock(return_value=MagicMock(
             handle=AsyncMock(),
             mark_user_sent=AsyncMock(),
             finalize=AsyncMock(),
         ))):
        await runner.run(user_request="hi")

    assert "context_anchor_order" not in captured
    assert captured.get("current_revision_id") == "rev_1"
    assert captured.get("task_id") == "task_ctx_001"
    assert "message_checkpoints" not in captured
    assert "handoff_context" not in captured
    configurable = captured_config.get("configurable", {})
    assert captured_config.get("recursion_limit") == 1000
    assert configurable.get("db_session") is not None
    assert configurable.get("runtime_context") == {}
    assert configurable.get("audit_context") is not None
    assert "context_anchor_persistence_sink" not in configurable
    assert "context_anchor_order" not in begin_revision.await_args.kwargs


@pytest.mark.asyncio
async def test_start_new_run_restarts_without_handoff_payload():
    runner = SessionRunner(
        session_id="sess_restart_001",
        task_id="task_restart_001",
        model_config={
            "provider_type": "openai",
            "model_id": "gpt",
            "api_key": "k",
            "base_url": "",
            "max_context_tokens": 8000,
        },
    )
    run_mock = AsyncMock()

    class _Graph:
        async def aget_state(self, config):
            class _S:
                values = {}

            return _S()

    with patch.object(runner, "_get_graph", AsyncMock(return_value=_Graph())), \
         patch.object(runner, "run", run_mock):
        await runner.start_new_run("continue")

    assert not hasattr(runner, "mode")
    assert runner._graph is None
    run_mock.assert_awaited_once_with("continue")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("revision_status", "expected"),
    [
        ("interrupted", True),
        ("cancelled", False),
        ("completed", False),
    ],
)
async def test_can_continue_requires_interrupted_revision_status(
    revision_status: str,
    expected: bool,
):
    runner = SessionRunner(
        session_id="sess_can_continue_001",
        task_id="task_can_continue_001",
        model_config={
            "provider_type": "openai",
            "model_id": "gpt",
            "api_key": "k",
            "base_url": "",
            "max_context_tokens": 8000,
        },
    )

    class _Graph:
        async def aget_state(self, config):
            return SimpleNamespace(
                next=("primary",),
                tasks=(),
                values={"current_revision_id": "rev_1"},
                config={"configurable": {}},
            )

    fake_session = MagicMock(close=AsyncMock())

    with patch.object(runner, "_get_graph", AsyncMock(return_value=_Graph())), patch(
        "app.storage.repos.revision_repo.get_by_id",
        AsyncMock(return_value=SimpleNamespace(status=revision_status)),
    ), patch(
        "app.agent_runtime.runner.session_runner.create_session",
        AsyncMock(return_value=fake_session),
    ):
        assert await runner.can_continue() is expected


@pytest.mark.asyncio
async def test_continue_with_user_message_resumes_checkpoint_with_command_update():
    runner = SessionRunner(
        session_id="sess_resume_001",
        task_id="task_resume_001",
        model_config={
            "provider_type": "openai",
            "model_id": "gpt",
            "api_key": "k",
            "base_url": "",
            "max_context_tokens": 8000,
        },
        project_id="proj_001",
    )
    captured: dict = {}
 
    class _Graph:
        def __init__(self) -> None:
            self.calls = 0
 
        async def astream_events(self, state, config, version):
            captured["state"] = state
            captured["config"] = config
            if False:
                yield None
 
        async def aget_state(self, config):
            self.calls += 1
            if self.calls == 1:
                return SimpleNamespace(
                    next=("primary",),
                    tasks=(),
                    values={
                        "current_revision_id": "rev_prev",
                    },
                    config={"configurable": {}},
                )
            return SimpleNamespace(next=(), tasks=(), values={}, config={"configurable": {}})
 
    fake_runtime_session = MagicMock(close=AsyncMock())
    fake_revision_session = MagicMock(close=AsyncMock(), commit=AsyncMock())
    fake_status_session = MagicMock(close=AsyncMock(), commit=AsyncMock())
    persisted_message = SimpleNamespace(id="msg_2", seq=2)
    fake_persister = MagicMock(
        handle=AsyncMock(),
        finalize=AsyncMock(),
        persist_node_event=AsyncMock(),
        apply_interrupt_preview=AsyncMock(),
    )
    raw_message = '<of-mention chapter_id="chap_1" label="旧章节" />'
    compiled_message = " @chapter:修订卷/修订章节 "

    with patch(
        "app.agent_runtime.runner.session_runner.compile_canonical_mentions",
        AsyncMock(return_value=compiled_message),
        create=True,
    ), patch.object(runner, "_get_graph", AsyncMock(return_value=_Graph())), patch.object(
        runner,
        "_persist_user_message",
        AsyncMock(return_value=persisted_message),
    ), patch.object(
        runner,
        "_emit_user_message",
        AsyncMock(),
    ), patch(
        "app.agent_runtime.runner.session_runner.begin_user_revision",
        AsyncMock(return_value=SimpleNamespace(id="rev_new")),
    ) as begin_revision, patch(
        "app.agent_runtime.runner.session_runner.finalize_revision_status",
        AsyncMock(),
    ), patch(
        "app.agent_runtime.runner.session_runner.emit",
        AsyncMock(),
    ), patch(
        "app.agent_runtime.runner.session_runner.create_session",
        AsyncMock(side_effect=[fake_runtime_session, fake_revision_session, fake_status_session]),
    ), patch.object(
        runner,
        "_make_persister",
        MagicMock(return_value=fake_persister),
    ):
        await runner.continue_with_user_message(raw_message)

    assert isinstance(captured["state"], Command)
    assert captured["state"].resume is None
    assert set(captured["state"]._update_as_tuples()) == {
        ("current_revision_id", "rev_new"),
        ("user_request", compiled_message),
    }
    assert captured["config"]["configurable"]["runtime_context"] == {}
    assert "context_anchor_order" not in begin_revision.await_args.kwargs
    queued = runner._inject_queue.get_nowait()
    assert queued == ("msg_2", "user", raw_message)


@pytest.mark.asyncio
async def test_run_compiles_user_request_for_model_and_persistence():
    runner = SessionRunner(
        session_id="sess_mentions_001",
        task_id="task_mentions_001",
        model_config={
            "provider_type": "openai",
            "model_id": "gpt",
            "api_key": "k",
            "base_url": "",
            "max_context_tokens": 8000,
        },
        project_id="proj_001",
    )
    captured: dict = {}

    class _Graph:
        async def astream_events(self, state, config, version):
            captured["state"] = state
            if False:
                yield None

        async def aget_state(self, config):
            return SimpleNamespace(next=(), tasks=(), values={}, config={"configurable": {}})

    fake_session = MagicMock(close=AsyncMock(), commit=AsyncMock())
    fake_persister = MagicMock(
        handle=AsyncMock(),
        mark_user_sent=AsyncMock(),
        finalize=AsyncMock(),
        persist_node_event=AsyncMock(),
    )
    persisted_message = SimpleNamespace(id="msg_mentions_001", seq=0, created_at=datetime.now(UTC))
    raw_message = '<of-mention chapter_id="chap_1" label="旧章节" />'
    compiled_message = " @chapter:修订卷/修订章节 "

    with patch(
        "app.agent_runtime.runner.session_runner.compile_canonical_mentions",
        AsyncMock(return_value=compiled_message),
        create=True,
    ), patch.object(runner, "_get_graph", AsyncMock(return_value=_Graph())),          patch.object(runner, "_prepare_run_persistence", AsyncMock(return_value=[])),          patch.object(runner, "_persist_user_message", AsyncMock(return_value=persisted_message)) as persist_user_message,          patch(
             "app.agent_runtime.runner.session_runner.begin_user_revision",
             AsyncMock(return_value=SimpleNamespace(id="rev_mentions_001")),
         ),          patch("app.agent_runtime.runner.session_runner.finalize_revision_status", AsyncMock()),          patch("app.agent_runtime.runner.session_runner.emit", new=AsyncMock()),          patch(
             "app.agent_runtime.runner.session_runner.create_session",
             AsyncMock(return_value=fake_session),
         ),          patch.object(runner, "_make_persister", MagicMock(return_value=fake_persister)):
        await runner.run(user_request=raw_message)

    persist_user_message.assert_awaited_once_with(raw_message)
    assert captured["state"]["user_request"] == compiled_message


@pytest.mark.asyncio
async def test_cancel_and_continue_queues_compiled_user_message():
    runner = SessionRunner(
        session_id="sess_cancel_001",
        task_id="task_cancel_001",
        model_config={
            "provider_type": "openai",
            "model_id": "gpt",
            "api_key": "k",
            "base_url": "",
            "max_context_tokens": 8000,
        },
        project_id="proj_001",
    )
    fake_session = MagicMock(close=AsyncMock())
    raw_message = '<of-mention chapter_id="chap_1" label="旧章节" />'

    with patch(
        "app.agent_runtime.runner.session_runner.create_session",
        AsyncMock(return_value=fake_session),
    ):
        await runner.cancel_and_continue(raw_message, "msg_cancel_001")

    assert runner._cancel_event.is_set()
    assert runner._inject_queue.get_nowait() == (
        None,
        "system",
        "[系统] 上一条回复被用户中止",
    )
    assert runner._inject_queue.get_nowait() == (
        "msg_cancel_001",
        "user",
        raw_message,
    )


@pytest.mark.asyncio
async def test_run_emits_error_and_marks_revision_failed_on_runtime_exception():
    runner = SessionRunner(
        session_id="sess_run_error_001",
        task_id="task_run_error_001",
        model_config={
            "provider_type": "openai",
            "model_id": "gpt",
            "api_key": "k",
            "base_url": "",
            "max_context_tokens": 8000,
        },
        project_id="proj_001",
    )
 
    class _Graph:
        async def astream_events(self, *_args, **_kwargs):
            raise GraphRecursionError("Recursion limit reached")
            if False:
                yield None
 
    fake_runtime_session = MagicMock(close=AsyncMock())
    fake_status_session = MagicMock(close=AsyncMock(), commit=AsyncMock())
    fake_persister = MagicMock(
        handle=AsyncMock(),
        finalize=AsyncMock(),
        persist_node_event=AsyncMock(),
    )
 
    with patch.object(runner, "_prepare_run_persistence", AsyncMock(return_value=[])), patch.object(
        runner,
        "_get_graph",
        AsyncMock(return_value=_Graph()),
    ), patch.object(
        runner,
        "_begin_user_turn",
        AsyncMock(return_value=(SimpleNamespace(id="msg_1"), SimpleNamespace(id="rev_error_1"))),
    ), patch(
        "app.agent_runtime.runner.session_runner.create_session",
        AsyncMock(side_effect=[fake_runtime_session, fake_status_session]),
    ), patch(
        "app.agent_runtime.runner.session_runner.finalize_revision_status",
        AsyncMock(),
    ) as finalize_revision_status, patch(
        "app.agent_runtime.runner.session_runner.emit",
        AsyncMock(),
    ) as emit_mock, patch.object(
        runner,
        "_make_persister",
        MagicMock(return_value=fake_persister),
    ), patch.object(
        runner,
        "_clear_replay_session",
        AsyncMock(),
    ):
        with pytest.raises(GraphRecursionError):
            await runner.run("触发异常")
 
    fake_persister.finalize.assert_awaited_once_with(reason="error")
    finalize_revision_status.assert_awaited_once_with(
        fake_status_session,
        "rev_error_1",
        "failed",
    )
    emit_mock.assert_any_await(
        "agent:error",
        {
            "session_id": "sess_run_error_001",
            "type": "runtime_failure",
            "reason": "Recursion limit reached",
        },
        room=runner._room,
    )
 
 
@pytest.mark.asyncio
async def test_continue_with_user_message_emits_error_on_runtime_exception():
    runner = SessionRunner(
        session_id="sess_continue_error_001",
        task_id="task_continue_error_001",
        model_config={
            "provider_type": "openai",
            "model_id": "gpt",
            "api_key": "k",
            "base_url": "",
            "max_context_tokens": 8000,
        },
        project_id="proj_001",
    )

    class _Graph:
        async def astream_events(self, *_args, **_kwargs):
            raise GraphRecursionError("Continue recursion limit reached")
            if False:
                yield None

        async def aget_state(self, _config):
            return SimpleNamespace(
                next=("primary",),
                tasks=(),
                values={"current_revision_id": "rev_prev"},
                config={"configurable": {}},
            )

    fake_runtime_session = MagicMock(close=AsyncMock())
    fake_status_session = MagicMock(close=AsyncMock(), commit=AsyncMock())
    fake_persister = MagicMock(
        handle=AsyncMock(),
        finalize=AsyncMock(),
        persist_node_event=AsyncMock(),
    )

    with patch.object(runner, "_get_graph", AsyncMock(return_value=_Graph())), patch.object(
        runner,
        "_begin_user_turn",
        AsyncMock(return_value=(SimpleNamespace(id="msg_2"), SimpleNamespace(id="rev_continue_1"))),
    ), patch.object(
        runner,
        "inject_message",
        AsyncMock(),
    ), patch(
        "app.agent_runtime.runner.session_runner.create_session",
        AsyncMock(side_effect=[fake_runtime_session, fake_status_session]),
    ), patch(
        "app.agent_runtime.runner.session_runner.finalize_revision_status",
        AsyncMock(),
    ) as finalize_revision_status, patch(
        "app.agent_runtime.runner.session_runner.emit",
        AsyncMock(),
    ) as emit_mock, patch.object(
        runner,
        "_make_persister",
        MagicMock(return_value=fake_persister),
    ), patch.object(
        runner,
        "_clear_replay_session",
        AsyncMock(),
    ):
        with pytest.raises(GraphRecursionError):
            await runner.continue_with_user_message("继续执行")

    fake_persister.finalize.assert_awaited_once_with(reason="error")
    finalize_revision_status.assert_awaited_once_with(
        fake_status_session,
        "rev_continue_1",
        "failed",
    )
    emit_mock.assert_any_await(
        "agent:error",
        {
            "session_id": "sess_continue_error_001",
            "type": "runtime_failure",
            "reason": "Continue recursion limit reached",
        },
        room=runner._room,
    )


@pytest.mark.asyncio
async def test_resume_emits_error_and_marks_revision_failed_on_runtime_exception():
    runner = SessionRunner(
        session_id="sess_resume_error_001",
        task_id="task_resume_error_001",
        model_config={
            "provider_type": "openai",
            "model_id": "gpt",
            "api_key": "k",
            "base_url": "",
            "max_context_tokens": 8000,
        },
        project_id="proj_001",
    )
 
    class _Graph:
        async def astream_events(self, *_args, **_kwargs):
            raise GraphRecursionError("Resume recursion limit reached")
            if False:
                yield None

        async def aget_state(self, _config):
            return SimpleNamespace(
                next=("primary",),
                tasks=(),
                values={"current_revision_id": "rev_resume_1"},
                config={"configurable": {}},
            )

    fake_runtime_session = MagicMock(close=AsyncMock())
    fake_status_session = MagicMock(close=AsyncMock(), commit=AsyncMock())
    fake_persister = MagicMock(
        handle=AsyncMock(),
        finalize=AsyncMock(),
        persist_node_event=AsyncMock(),
    )

    with patch.object(runner, "_get_graph", AsyncMock(return_value=_Graph())), patch(
        "app.agent_runtime.runner.session_runner.create_session",
        AsyncMock(side_effect=[fake_runtime_session, fake_status_session]),
    ), patch(
        "app.agent_runtime.runner.session_runner.finalize_revision_status",
        AsyncMock(),
    ) as finalize_revision_status, patch(
        "app.agent_runtime.runner.session_runner.emit",
        AsyncMock(),
    ) as emit_mock, patch.object(
        runner,
        "_make_persister",
        MagicMock(return_value=fake_persister),
    ), patch.object(
        runner,
        "_clear_replay_session",
        AsyncMock(),
    ):
        with pytest.raises(GraphRecursionError):
            await runner.resume({"answer": "继续"})

    fake_persister.finalize.assert_awaited_once_with(reason="error")
    finalize_revision_status.assert_awaited_once_with(
        fake_status_session,
        "rev_resume_1",
        "failed",
    )
    emit_mock.assert_any_await(
        "agent:error",
        {
            "session_id": "sess_resume_error_001",
            "type": "runtime_failure",
            "reason": "Resume recursion limit reached",
        },
        room=runner._room,
    )


@pytest.mark.asyncio
async def test_manual_compact_builds_window_and_returns_metrics_without_revision():
    runner = SessionRunner(
        session_id="sess_manual_compact_001",
        task_id="task_manual_compact_001",
        model_config={
            "provider_type": "openai",
            "model_id": "gpt",
            "api_key": "k",
            "base_url": "",
            "max_context_tokens": 8000,
        },
        project_id="proj_manual_compact_001",
    )
    fake_session = MagicMock(close=AsyncMock())
    history_message = HumanMessage(
        content="上一轮用户消息",
        response_metadata={"openfic_seq": 1},
    )
    node_message = {
        "role": "user",
        "content": "上一轮用户消息",
        "metadata": {"part": "history", "seq": 1},
    }
    history_part = ContextMessage(
        role="user",
        content="上一轮用户消息",
        metadata={"part": "history", "seq": 1},
    )
    static_part = ContextMessage(
        role="system",
        content="system",
        metadata={"part": "system"},
    )
    window = SimpleNamespace(
        start_seq=1,
        end_seq=4,
        source_input_tokens=456,
        transcript="transcript",
    )
    compaction = SimpleNamespace(
        id="cmp_manual_1",
        start_seq=1,
        end_seq=4,
        source_input_tokens=456,
        summary_tokens=37,
    )
    list_by_session = AsyncMock(return_value=[])

    with patch(
        "app.agent_runtime.runner.session_runner.create_session",
        AsyncMock(return_value=fake_session),
    ), patch(
        "app.agent_runtime.runner.session_runner.load_history",
        AsyncMock(return_value=[history_message]),
    ) as load_history_mock, patch(
        "app.agent_runtime.runner.session_runner._to_history_dict",
        MagicMock(return_value=node_message),
        create=True,
    ) as to_history_dict, patch(
        "app.agent_runtime.runner.session_runner.build_context_parts",
        AsyncMock(return_value=[static_part, history_part]),
        create=True,
    ) as build_context_parts, patch(
        "app.agent_runtime.runner.session_runner.compaction_repo",
        SimpleNamespace(list_by_session=list_by_session),
        create=True,
    ), patch(
        "app.agent_runtime.runner.session_runner.select_compaction_window",
        MagicMock(return_value=window),
        create=True,
    ) as select_compaction_window, patch(
        "app.agent_runtime.runner.session_runner.compact_window",
        AsyncMock(return_value=compaction),
        create=True,
    ) as compact_window, patch(
        "app.agent_runtime.runner.session_runner.begin_user_revision",
        AsyncMock(),
    ) as begin_user_revision:
        result = await runner.compact()

    assert result == {
        "compaction_id": "cmp_manual_1",
        "start_seq": 1,
        "end_seq": 4,
        "source_input_tokens": 456,
        "summary_tokens": 37,
    }
    load_history_mock.assert_awaited_once_with(fake_session, "sess_manual_compact_001")
    to_history_dict.assert_called_once_with(history_message)
    build_context_parts.assert_awaited_once()
    state, agent_name, node_messages, db_session = build_context_parts.await_args.args
    assert state["session_id"] == "sess_manual_compact_001"
    assert state["task_id"] == "task_manual_compact_001"
    assert state["project_id"] == "proj_manual_compact_001"
    assert state["model_config"]["max_context_tokens"] == 8000
    assert state["active_agent"] is None
    assert agent_name == "primary"
    assert node_messages == [node_message]
    assert db_session is fake_session
    list_by_session.assert_awaited_once_with(fake_session, "sess_manual_compact_001")
    select_compaction_window.assert_called_once_with([history_part], [], 8000)
    compact_window.assert_awaited_once()
    assert compact_window.await_args.args == (fake_session,)
    assert compact_window.await_args.kwargs["state"] is state
    assert compact_window.await_args.kwargs["window"] is window
    assert compact_window.await_args.kwargs["trigger"] == "manual"
    assert compact_window.await_args.kwargs["event_sink"] == runner._emit_agent_event
    assert (
        compact_window.await_args.kwargs["usage_sink"]
        == runner._emit_persisted_task_usage_events
    )
    begin_user_revision.assert_not_awaited()
    fake_session.close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_consume_next_pending_user_message_persists_and_removes_injected_item():
    runner = SessionRunner(
        session_id="sess_pending_continue_001",
        task_id="task_pending_continue_001",
        model_config={
            "provider_type": "openai",
            "model_id": "gpt",
            "api_key": "k",
            "base_url": "",
            "max_context_tokens": 8000,
        },
        project_id="proj_pending_continue_001",
    )
    created_at = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
    runner._queued_user_messages["msg_pending_1"] = ("压缩后继续处理", created_at)
    runner._queued_user_messages["msg_pending_2"] = ("下一条 pending", created_at)
    await runner._inject_queue.put((None, "system", "系统消息"))
    await runner._inject_queue.put(("msg_pending_1", "user", "压缩后继续处理"))
    await runner._inject_queue.put(("msg_pending_2", "user", "下一条 pending"))

    with patch.object(
        runner,
        "_persist_user_message",
        AsyncMock(),
    ) as persist_user_message, patch.object(
        runner,
        "_emit_pending_user_message",
        AsyncMock(),
    ) as emit_pending_user_message, patch.object(
        runner,
        "_emit_runtime_user_message",
        AsyncMock(),
    ) as emit_runtime_user_message:
        result = await runner.consume_next_pending_user_message_for_continuation()

    assert result == ("msg_pending_1", "压缩后继续处理")
    persist_user_message.assert_awaited_once_with(
        "压缩后继续处理",
        message_id="msg_pending_1",
        created_at=created_at,
    )
    emit_pending_user_message.assert_awaited_once_with(
        "压缩后继续处理",
        message_id="msg_pending_1",
        action="consumed",
        created_at=created_at.isoformat(),
    )
    emit_runtime_user_message.assert_awaited_once_with(
        "压缩后继续处理",
        message_id="msg_pending_1",
        created_at=created_at.isoformat(),
    )
    assert "msg_pending_1" not in runner._queued_user_messages
    assert runner._queued_user_messages["msg_pending_2"] == (
        "下一条 pending",
        created_at,
    )

    remaining: list[tuple[str | None, str, str]] = []
    while not runner._inject_queue.empty():
        remaining.append(runner._inject_queue.get_nowait())
    assert remaining == [
        (None, "system", "系统消息"),
        ("msg_pending_2", "user", "下一条 pending"),
    ]


@pytest.mark.asyncio
async def test_consume_next_pending_user_message_keeps_pending_when_persist_fails():
    runner = SessionRunner(
        session_id="sess_pending_persist_error_001",
        task_id="task_pending_persist_error_001",
        model_config={
            "provider_type": "openai",
            "model_id": "gpt",
            "api_key": "k",
            "base_url": "",
            "max_context_tokens": 8000,
        },
        project_id="proj_pending_persist_error_001",
    )
    created_at = datetime(2026, 6, 21, 12, 0, tzinfo=UTC)
    runner._queued_user_messages["msg_pending_1"] = ("压缩后继续处理", created_at)
    await runner._inject_queue.put(("msg_pending_1", "user", "压缩后继续处理"))

    with patch.object(
        runner,
        "_persist_user_message",
        AsyncMock(side_effect=RuntimeError("db write failed")),
    ), patch.object(
        runner,
        "_emit_pending_user_message",
        AsyncMock(),
    ) as emit_pending_user_message, patch.object(
        runner,
        "_emit_runtime_user_message",
        AsyncMock(),
    ) as emit_runtime_user_message:
        with pytest.raises(RuntimeError, match="db write failed"):
            await runner.consume_next_pending_user_message_for_continuation()

    assert runner._queued_user_messages["msg_pending_1"] == (
        "压缩后继续处理",
        created_at,
    )
    remaining: list[tuple[str | None, str, str]] = []
    while not runner._inject_queue.empty():
        remaining.append(runner._inject_queue.get_nowait())
    assert remaining == [("msg_pending_1", "user", "压缩后继续处理")]
    emit_pending_user_message.assert_not_awaited()
    emit_runtime_user_message.assert_not_awaited()
