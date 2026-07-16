"""Unified LLM audit context tests."""

import json
from typing import Any

import pytest
from langchain_core.messages import SystemMessage

from app.audit.context import AuditContext


@pytest.mark.asyncio
async def test_audit_context_records_summary_call_with_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enqueued: list[Any] = []

    async def fake_enqueue(audit_log: Any) -> None:
        enqueued.append(audit_log)

    monkeypatch.setattr("app.audit.context.enqueue_audit_log", fake_enqueue)
    context = AuditContext(
        project_id="project-1",
        chapter_id="chapter-1",
        category="memory",
        metadata={"background_job_id": "job-1", "summary_type": "chapter"},
    )

    async with context.llm_call(
        operation="chapter_summary",
        model_id="gpt-test",
        model_provider="openai-compatible",
        model_name="GPT Test",
        request_messages=[SystemMessage(content="prompt")],
    ) as audit:
        audit.record_response(
            tool_calls=[{"name": "emit_chapter_summary", "args": {"summary": "摘要"}}],
            usage={"input_tokens": 12, "output_tokens": 8},
        )

    assert len(enqueued) == 1
    audit_log = enqueued[0]
    assert audit_log.category == "memory"
    assert audit_log.operation == "chapter_summary"
    assert audit_log.chapter_id == "chapter-1"
    assert json.loads(audit_log.extra_data or "{}") == {
        "background_job_id": "job-1",
        "summary_type": "chapter",
    }
    assert audit_log.tokens_total == 20


@pytest.mark.asyncio
async def test_audit_context_defaults_category_to_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enqueued: list[Any] = []

    async def fake_enqueue(audit_log: Any) -> None:
        enqueued.append(audit_log)

    monkeypatch.setattr("app.audit.context.enqueue_audit_log", fake_enqueue)
    context = AuditContext(project_id="project-1")

    async with context.llm_call(operation="writer", model_id="gpt-test"):
        pass

    assert enqueued[0].category == "agent"
