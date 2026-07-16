"""Agent runtime audit collector tests."""

import json
from typing import Any

import pytest
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage

from app.audit import AuditContext


@pytest.mark.asyncio
async def test_audit_request_messages_are_pretty_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enqueued: list[Any] = []

    async def fake_enqueue(audit_log: Any) -> None:
        enqueued.append(audit_log)

    monkeypatch.setattr("app.audit.context.enqueue_audit_log", fake_enqueue)

    context = AuditContext(project_id="project-1")
    messages: list[BaseMessage] = [
        SystemMessage(content="提示词：\n"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "call_1",
                    "name": "edit_chapter",
                    "args": {
                        "chapter_ref": {"type": "order", "value": 1},
                        "content": "第一段\n第二段",
                    },
                }
            ],
        ),
    ]

    async with context.llm_call(
        operation="writer",
        model_id="model-1",
        request_messages=messages,
    ):
        pass

    assert len(enqueued) == 1
    request_messages = enqueued[0].request_messages
    assert isinstance(request_messages, str)
    assert request_messages.startswith("[\n")
    assert '\n    "content": "提示词：\\n"' in request_messages
    assert '\n        "name": "edit_chapter"' in request_messages
    assert (
        json.loads(request_messages)[1]["tool_calls"][0]["args"]["content"]
        == "第一段\n第二段"
    )


@pytest.mark.asyncio
async def test_audit_records_openai_cached_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enqueued: list[Any] = []

    async def fake_enqueue(audit_log: Any) -> None:
        enqueued.append(audit_log)

    monkeypatch.setattr("app.audit.context.enqueue_audit_log", fake_enqueue)

    context = AuditContext(project_id="project-1")
    request_messages: list[BaseMessage] = [SystemMessage(content="prompt")]

    async with context.llm_call(
        operation="writer",
        model_id="model-1",
        request_messages=request_messages,
    ) as audit:
        audit.record_response(
            usage={
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "prompt_tokens_details": {"cached_tokens": 64},
            },
        )

    audit_log = enqueued[0]
    assert audit_log.tokens_input == 100
    assert audit_log.tokens_output == 20
    assert audit_log.tokens_total == 120
    assert audit_log.token_cache == 64


@pytest.mark.asyncio
async def test_audit_records_subagent_parent_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enqueued: list[Any] = []

    async def fake_enqueue(audit_log: Any) -> None:
        enqueued.append(audit_log)

    async def fake_next_call_sequence(_session_id: str | None) -> int:
        return 1

    monkeypatch.setattr("app.audit.context.enqueue_audit_log", fake_enqueue)
    monkeypatch.setattr(
        "app.audit.context.next_call_sequence",
        fake_next_call_sequence,
    )

    context = AuditContext(
        project_id="project-1",
        session_id="child-thread-1",
        task_id="task-1",
        parent_session_id="parent-session-1",
        child_run_id="child-run-1",
    )

    async with context.llm_call(
        operation="writer",
        model_id="model-1",
    ):
        pass

    audit_log = enqueued[0]
    assert audit_log.session_id == "child-thread-1"
    assert audit_log.task_id == "task-1"
    assert audit_log.parent_session_id == "parent-session-1"
    assert audit_log.child_run_id == "child-run-1"
