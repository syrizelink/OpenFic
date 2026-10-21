from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langchain_core.runnables import RunnableLambda

from app.agent_runtime.context.compaction.service import compact_window
from app.agent_runtime.context.compaction.window import CompactionWindow
from app.agent_runtime.context.types import ContextMessage
from app.agent_runtime.persistence.compaction_types import PersistedCompaction
from app.agent_runtime.persistence.persister import MessagePersister
from app.agent_runtime.runner.event_scope import (
    COMPACTION_EVENT_TAG,
    SUBAGENT_CHILD_EVENT_TAG,
)
from app.agent_runtime.runner.event_translator import EventTranslator


class AsyncFakeChatModel(FakeMessagesListChatModel):
    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        return self._generate(messages, stop=stop, **kwargs)


@pytest.mark.asyncio
@pytest.mark.parametrize("is_child", [False, True])
async def test_compaction_callbacks_do_not_duplicate_usage_or_persist_summary(
    monkeypatch, is_child,
):
    state = {"session_id": "session", "task_id": "task", "project_id": "project"}
    window = CompactionWindow(
        start_seq=1,
        end_seq=2,
        messages=[ContextMessage(role="assistant", content="old output")],
        source_input_tokens=100,
        transcript="old output",
    )
    compaction = PersistedCompaction(
        id="compaction",
        **state,
        start_seq=1,
        end_seq=2,
        summary="internal summary",
        trigger="auto",
        source_input_tokens=100,
        summary_tokens=10,
        created_at=datetime.now(UTC),
    )
    compaction_model = AsyncFakeChatModel(responses=[AIMessage(
        content="internal summary",
        usage_metadata={"input_tokens": 100, "output_tokens": 10, "total_tokens": 110},
    )])
    normal_model = AsyncFakeChatModel(responses=[AIMessage(
        content="normal answer",
        usage_metadata={"input_tokens": 20, "output_tokens": 5, "total_tokens": 25},
    )])
    prefix = "app.agent_runtime.context.compaction.service."
    monkeypatch.setattr(prefix + "create_chat_model", lambda *_: compaction_model)
    monkeypatch.setattr(prefix + "_build_messages", AsyncMock(
        return_value=[HumanMessage(content="summarize")],
    ))
    monkeypatch.setattr(prefix + "_current_plan_block", AsyncMock(return_value=None))
    insert = AsyncMock(return_value=compaction)
    monkeypatch.setattr(prefix + "compaction_repo.insert_compaction", insert)
    marker = AsyncMock()
    monkeypatch.setattr(prefix + "_persist_display_marker", marker)
    usage_sink = AsyncMock()
    event_sink = AsyncMock()

    async def run(_):
        await compact_window(
            AsyncMock(),
            state=state,
            window=window,
            trigger="auto",
            model_config={
                "provider_type": "openai", "base_url": "https://example.test",
                "api_key": "test", "model_id": "test",
            },
            usage_sink=usage_sink,
            event_sink=event_sink,
        )
        return await normal_model.ainvoke([HumanMessage(content="continue")])

    translator = EventTranslator("session", allow_subagent_child_events=is_child)
    persister = MessagePersister(
        "session", "task", "project", AsyncMock(),
        allow_subagent_child_events=is_child,
    )
    write = AsyncMock()
    monkeypatch.setattr(persister, "_write", write)
    translated = []
    events = [event async for event in RunnableLambda(run).astream_events(
        {}, config={"tags": [SUBAGENT_CHILD_EVENT_TAG] if is_child else []}, version="v2",
    )]
    for event in events:
        result = translator.translate(event)
        if result:
            translated.extend(result if isinstance(result, list) else [result])
        await persister.handle(event)
    await persister.finalize(reason="done")

    # Exercise inherited LangChain callbacks, rather than constructing only tagged events.
    summary_end = next(event for event in events if (
        event["event"] == "on_chat_model_end"
        and event["data"]["output"].content == "internal summary"
    ))
    assert COMPACTION_EVENT_TAG in summary_end["tags"]
    if is_child:
        assert SUBAGENT_CHILD_EVENT_TAG in summary_end["tags"]
    usage_sink.assert_awaited_once()
    assert usage_sink.await_args.args[0]["usage_kind"] == "compaction"
    assert usage_sink.await_args.args[0]["token_input"] == 100
    assert usage_sink.await_args.args[0]["token_output"] == 10
    usages = [event["data"]["usage"] for event in translated if event["name"] == "agent:usage"]
    assert usages == [{"input_tokens": 20, "output_tokens": 5, "total_tokens": 25}]
    write.assert_awaited_once()
    assert write.await_args.kwargs["role"] == "assistant"
    assert write.await_args.kwargs["content"] == "normal answer"
    insert.assert_awaited_once()
    marker.assert_awaited_once()
    assert [call.args[0] for call in event_sink.await_args_list] == [
        "agent:compaction_start", "agent:compaction_success",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("is_child", [False, True])
@pytest.mark.parametrize("reason", ["done", "cancelled", "error"])
async def test_compaction_stream_cannot_leak_tokens_or_partial_messages(is_child, reason):
    translator = EventTranslator("session", allow_subagent_child_events=is_child)
    persister = MessagePersister(
        "session", "task", "project", AsyncMock(),
        allow_subagent_child_events=is_child,
    )
    persister._write = AsyncMock()
    tags = [COMPACTION_EVENT_TAG]
    if is_child:
        tags.append(SUBAGENT_CHILD_EVENT_TAG)
    for event in [
        {"event": "on_chat_model_start", "data": {}},
        {"event": "on_chat_model_stream", "data": {"chunk": AIMessageChunk(
            content="internal partial summary",
            additional_kwargs={"reasoning_content": "internal reasoning"},
        )}},
    ]:
        event.update(tags=tags, run_id="summary-run")
        assert translator.translate(event) is None
        await persister.handle(event)
    await persister.finalize(reason=reason)
    persister._write.assert_not_awaited()
