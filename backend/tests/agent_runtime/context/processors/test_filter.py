import json
from typing import Literal

from app.agent_runtime.context.processors.filter import (
    filter_invalid,
    filter_tool_result_metadata,
    filter_tool_result_metadata_content,
)
from app.agent_runtime.context.types import ContextMessage

ContextRole = Literal["system", "user", "assistant", "tool"]


def _h(role: ContextRole, content: str = "", **meta) -> ContextMessage:
    metadata = {"part": "history"}
    metadata.update(meta)
    return ContextMessage(role=role, content=content, metadata=metadata)


def test_keeps_static_parts_unchanged() -> None:
    parts = [
        ContextMessage(role="system", content="", metadata={"part": "environment"}),
        ContextMessage(role="system", content="rules", metadata={"part": "rules"}),
    ]
    out = filter_invalid(parts)
    assert out == parts


def test_drops_empty_history_messages() -> None:
    parts = [
        _h("user", ""),
        _h("user", "   "),
        _h("user", "real"),
    ]
    out = filter_invalid(parts)
    assert len(out) == 1
    assert out[0].content == "real"


def test_drops_thinking_kind() -> None:
    parts = [
        _h("assistant", "thought", kind="thinking"),
        _h("assistant", "reply"),
    ]
    out = filter_invalid(parts)
    assert [m.content for m in out] == ["reply"]


def test_drops_orphan_tool_calls_pair() -> None:
    parts = [
        _h("assistant", "calling", **{}),
    ]
    parts[0].tool_calls = [{"id": "c1", "name": "x", "args": {}}]
    out = filter_invalid(parts)
    assert out == []


def test_keeps_paired_tool_call_and_response() -> None:
    asst = _h("assistant", "calling")
    asst.tool_calls = [{"id": "c1", "name": "x", "args": {}}]
    tool = _h("tool", "result")
    tool.tool_call_id = "c1"
    out = filter_invalid([asst, tool])
    assert len(out) == 2


def test_keeps_paired_empty_assistant_tool_call_and_response() -> None:
    asst = _h("assistant", "")
    asst.tool_calls = [{"id": "c1", "name": "x", "args": {}}]
    tool = _h("tool", "result")
    tool.tool_call_id = "c1"
    out = filter_invalid([asst, tool])
    assert len(out) == 2


def test_drops_orphan_tool_response_when_assistant_dropped() -> None:
    asst = _h("assistant", "thought", kind="thinking")
    asst.tool_calls = [{"id": "c1", "name": "x", "args": {}}]
    tool = _h("tool", "result")
    tool.tool_call_id = "c1"
    out = filter_invalid([asst, tool])
    assert out == []


def test_drops_tool_response_separated_from_its_assistant_tool_call() -> None:
    asst = _h("assistant", "calling")
    asst.tool_calls = [{"id": "c1", "name": "x", "args": {}}]
    intervening = _h("assistant", "plain response")
    tool = _h("tool", "result")
    tool.tool_call_id = "c1"

    out = filter_invalid([asst, intervening, tool])

    assert [message.content for message in out] == ["plain response"]


def test_keeps_all_contiguous_parallel_tool_responses() -> None:
    asst = _h("assistant", "calling")
    asst.tool_calls = [
        {"id": "c1", "name": "first", "args": {}},
        {"id": "c2", "name": "second", "args": {}},
    ]
    first_tool = _h("tool", "first result")
    first_tool.tool_call_id = "c2"
    second_tool = _h("tool", "second result")
    second_tool.tool_call_id = "c1"

    out = filter_invalid([asst, first_tool, second_tool])

    assert out == [asst, first_tool, second_tool]


def test_tool_result_metadata_content_keeps_success_result() -> None:
    content = '{"success":true,"metadata":{"note_diff":{"note_id":"note-1"}}}'

    assert filter_tool_result_metadata_content(content) == '{"success": true}'


def test_tool_result_context_formats_web_search_results() -> None:
    content = json.dumps(
        {
            "query": "komputasi kuantum",
            "provider": "serper",
            "answer": "answer should not be sent",
            "results": [
                {
                    "title": "Judul Satu",
                    "url": "https://example.com/one",
                    "snippet": "Ringkasan satu",
                },
                {
                    "title": "Judul Dua",
                    "url": "https://example.com/two",
                    "snippet": "Ringkasan dua",
                },
            ],
        },
        ensure_ascii=False,
    )

    assert filter_tool_result_metadata_content(content, tool_name="web_search") == (
        "[ Hasil pencarian untuk `komputasi kuantum` ]\n\n"
        "1. Judul Satu\n"
        "    Ringkasan satu\n"
        "    URL: https://example.com/one\n\n"
        "2. Judul Dua\n"
        "    Ringkasan dua\n"
        "    URL: https://example.com/two"
    )


def test_tool_result_context_formats_web_fetch_content() -> None:
    content = json.dumps(
        {
            "url": "https://example.com/article",
            "title": "Judul Artikel",
            "icon_url": "https://example.com/favicon.ico",
            "content": "Isi utama halaman\n\n## Bagian Kedua",
            "metadata": {"display_only": True},
        },
        ensure_ascii=False,
    )

    assert filter_tool_result_metadata_content(content, tool_name="web_fetch") == (
        "Isi utama halaman\n\n## Bagian Kedua"
    )


def test_filter_tool_result_metadata_formats_named_web_search_message() -> None:
    content = json.dumps(
        {
            "query": "OpenFic",
            "results": [
                {
                    "title": "Beranda Proyek",
                    "url": "https://example.com/openfic",
                    "snippet": "Ringkasan proyek",
                }
            ],
        },
        ensure_ascii=False,
    )
    message = ContextMessage(
        role="tool",
        content=content,
        name="web_search",
        metadata={"part": "history"},
    )

    filtered = filter_tool_result_metadata([message])

    assert filtered[0].content == (
        "[ Hasil pencarian untuk `OpenFic` ]\n\n"
        "1. Beranda Proyek\n"
        "    Ringkasan proyek\n"
        "    URL: https://example.com/openfic"
    )


def test_tool_failure_content_exposes_only_message_to_model() -> None:
    content = (
        '{"type":"fail","success":false,"code":"not_found",'
        '"message":"Bab tidak ditemukan: Bab 3",'
        '"trace":{"exception_type":"ToolExecutionError"}}'
    )

    assert filter_tool_result_metadata_content(content) == "Bab tidak ditemukan: Bab 3"


def test_tool_failure_content_keeps_legacy_error_compatible() -> None:
    content = '{"error":"Bab tidak ditemukan: Bab 3","metadata":{"internal":"value"}}'

    assert filter_tool_result_metadata_content(content) == "Bab tidak ditemukan: Bab 3"


def test_tool_failure_content_keeps_legacy_subagent_resume_identity() -> None:
    content = (
        '{"dispatch_id":"dispatch-1","agent_key":"writer",'
        '"agent_number":"#1001","error":"Sesi subagen dihentikan oleh pengguna"}'
    )

    assert json.loads(filter_tool_result_metadata_content(content)) == {
        "type": "fail",
        "success": False,
        "code": "execution_failed",
        "message": "Sesi subagen dihentikan oleh pengguna",
        "dispatch_id": "dispatch-1",
        "agent_key": "writer",
        "agent_number": "#1001",
    }


def test_tool_failure_content_keeps_subagent_resume_identity() -> None:
    content = (
        '{"type":"fail","success":false,"code":"execution_failed",'
        '"message":"Sesi subagen dihentikan oleh pengguna",'
        '"dispatch_id":"dispatch-1","agent_key":"writer",'
        '"agent_number":"#1001","trace":{"source":"persistence_finalize"}}'
    )

    assert json.loads(filter_tool_result_metadata_content(content)) == {
        "type": "fail",
        "success": False,
        "code": "execution_failed",
        "message": "Sesi subagen dihentikan oleh pengguna",
        "dispatch_id": "dispatch-1",
        "agent_key": "writer",
        "agent_number": "#1001",
    }


def test_tool_control_content_preserves_control_state() -> None:
    content = (
        '{"type":"control","success":false,"status":"approval_denied",'
        '"message":"Pemanggilan tool ditolak oleh pengguna","approval_id":"approval-1",'
        '"metadata":{"internal":"value"}}'
    )

    assert json.loads(filter_tool_result_metadata_content(content)) == {
        "type": "control",
        "success": False,
        "status": "approval_denied",
        "message": "Pemanggilan tool ditolak oleh pengguna",
        "approval_id": "approval-1",
    }


def test_tool_failure_content_identifies_missing_message_by_code() -> None:
    content = '{"type":"fail","success":false,"code":"not_found"}'

    assert filter_tool_result_metadata_content(content) == (
        "Kesalahan alat (not_found): tidak menyediakan pesan error yang spesifik"
    )
