"""Unified LLM audit context tests."""

import json
from typing import Any

import pytest
from langchain_core.messages import SystemMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.audit.context import AuditContext
from app.audit.queue import AuditQueue, persist_audit_details
from app.storage.models.llm_audit_log import LLMAuditLog


def _lookup_chapter(chapter_id: str) -> str:
    return chapter_id


class _NoteRef(BaseModel):
    id: str | None = Field(default=None, description="Cari berdasarkan ID")
    title: str | None = Field(default=None, description="Cari berdasarkan judul")


class _ReadNoteInput(BaseModel):
    note_ref: _NoteRef = Field(description="Referensi catatan yang akan dibaca")


def _read_note(note_ref: _NoteRef) -> str:
    return note_ref.title or ""


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
            tool_calls=[{"name": "emit_chapter_summary", "args": {"summary": "Ringkasan"}}],
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


@pytest.mark.asyncio
async def test_audit_context_persists_tool_references(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enqueued: list[Any] = []

    async def fake_enqueue(audit_log: Any) -> None:
        enqueued.append(audit_log)

    monkeypatch.setattr("app.audit.context.enqueue_audit_log", fake_enqueue)
    tool = StructuredTool.from_function(
        func=_lookup_chapter,
        name="lookup_chapter",
        description="Look up a chapter by its ID.",
    )
    context = AuditContext(project_id="project-1")

    async with context.llm_call(
        operation="writer",
        model_id="gpt-test",
        tools=[tool],
    ):
        pass

    assert json.loads(enqueued[0].tool_references or "[]") == [
        {
            "name": "lookup_chapter",
            "description": "Look up a chapter by its ID.",
            "parameters": {
                "chapter_id": {
                    "title": "Chapter Id",
                    "type": "string",
                }
            },
        }
    ]


@pytest.mark.asyncio
async def test_audit_context_inlines_nested_tool_parameter_references(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enqueued: list[Any] = []

    async def fake_enqueue(audit_log: Any) -> None:
        enqueued.append(audit_log)

    monkeypatch.setattr("app.audit.context.enqueue_audit_log", fake_enqueue)
    tool = StructuredTool.from_function(
        func=_read_note,
        name="read_note",
        description="Membaca isi lengkap satu catatan",
        args_schema=_ReadNoteInput,
    )
    context = AuditContext(project_id="project-1")

    async with context.llm_call(
        operation="writer",
        model_id="gpt-test",
        tools=[tool],
    ):
        pass

    parameters = json.loads(enqueued[0].tool_references or "[]")[0]["parameters"]
    assert "$ref" not in json.dumps(parameters)
    assert parameters["note_ref"]["description"] == "Referensi catatan yang akan dibaca"
    assert parameters["note_ref"]["properties"]["id"]["description"] == "Cari berdasarkan ID"
    assert parameters["note_ref"]["properties"]["title"]["description"] == "Cari berdasarkan judul"


@pytest.mark.asyncio
async def test_disabled_detail_persistence_removes_audit_payloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setelah pencatatan detail dimatikan, statistik audit tetap ada tetapi payload detail tidak boleh dipersistensi."""
    enqueued: list[Any] = []

    async def fake_enqueue(audit_log: Any) -> None:
        enqueued.append(audit_log)

    monkeypatch.setattr("app.audit.context.enqueue_audit_log", fake_enqueue)
    context = AuditContext(project_id="project-1", metadata={"source": "test"})

    async with context.llm_call(
        operation="writer",
        model_id="gpt-test",
        request_messages=[SystemMessage(content="prompt")],
    ) as audit:
        audit.record_response(
            content="completion",
            tool_calls=[{"name": "tool", "args": {}}],
            usage={"input_tokens": 12, "output_tokens": 8},
        )
        audit.record_tool_call("tool", {"value": 1}, {"result": "ok"})

    audit_log = enqueued[0]
    sanitized = persist_audit_details(audit_log, False)

    assert sanitized.request_messages is None
    assert sanitized.tool_references is None
    assert sanitized.response_content is None
    assert sanitized.response_tool_calls is None
    assert sanitized.tool_call_results is None
    assert sanitized.extra_data is None
    assert sanitized.tokens_total == 20
    assert sanitized.tool_calls_count == 1


@pytest.mark.asyncio
async def test_audit_queue_captures_detail_setting_when_audit_log_is_enqueued(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Log audit yang sudah masuk antrean tidak boleh terpengaruh perubahan pengaturan setelahnya."""
    queue = AuditQueue()
    monkeypatch.setattr(queue, "start", lambda: None)
    queue.set_persist_details(False)
    audit_log = LLMAuditLog(
        id="queued-audit-log",
        project_id="project-1",
        operation="writer",
        model_id="model-1",
        status="success",
        request_messages='[{"content":"prompt"}]',
        response_content="completion",
    )

    await queue.enqueue(audit_log)
    queue.set_persist_details(True)
    queued_log = queue._queue.get_nowait()

    assert queued_log is not None
    assert queued_log.request_messages is None
    assert queued_log.response_content is None
