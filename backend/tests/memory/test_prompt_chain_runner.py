# -*- coding: utf-8 -*-
"""Prompt chain runner history compaction tests."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.memory import prompt_chain_runner
from app.memory.prompt_chain_runner import ChatRuntime, _compact_task_history, _compact_task_history_message, build_chat_messages
from app.storage.models.task_message import TaskMessage


@pytest.fixture(autouse=True)
def _compress_setting_disabled() -> None:
    with patch(
        "app.agent_runtime.context.processors.compress.setting_repo.get_by_key",
        new=AsyncMock(return_value=None),
    ):
        yield


def test_compact_assistant_tool_calls_preserves_tool_input() -> None:
    message = TaskMessage(
        task_id="task-1",
        role="assistant",
        agent_id="designer",
        content="Saya akan menulis kerangka",
        tool_calls=json.dumps(
            [
                {
                    "id": "call_1",
                    "name": "confirm_outline",
                    "args": {"beats": [{"content": "Tokoh utama berangkat -> tiba di lokasi"}]},
                }
            ],
            ensure_ascii=False,
        ),
    )

    compact = _compact_task_history_message(message)

    assert compact == {
        "role": "assistant",
        "content": "Saya akan menulis kerangka",
        "agent_id": "designer",
        "tool_calls": [
            {
                "id": "call_1",
                "name": "confirm_outline",
                "args": {"beats": [{"content": "Tokoh utama berangkat -> tiba di lokasi"}]},
            }
        ],
    }


def test_compact_assistant_tool_calls_filters_other_agent_tools() -> None:
    message = TaskMessage(
        task_id="task-1",
        role="assistant",
        agent_id="designer",
        content="Kerangka sudah dikonfirmasi, sekarang mulai menulis.",
        tool_calls=json.dumps(
            [
                {
                    "id": "call_1",
                    "name": "confirm_outline",
                    "args": {"beats": [{"content": "Tokoh utama berangkat -> tiba di lokasi"}]},
                }
            ],
            ensure_ascii=False,
        ),
    )

    compact = _compact_task_history_message(message, current_agent_name="writer")

    assert compact is not None
    assert compact["role"] == "assistant"
    assert compact["agent_id"] == "designer"
    assert "tool_calls" not in compact
    assert "<agent_role>designer</agent_role>" in compact["content"]
    assert "tidak dapat dipakai sebagai tool" in compact["content"]
    assert "confirm_outline" in compact["content"]


def test_compact_assistant_tool_calls_keeps_current_agent_tools() -> None:
    message = TaskMessage(
        task_id="task-1",
        role="assistant",
        agent_id="writer",
        content="Bersiap menyunting bab.",
        tool_calls=json.dumps(
            [
                {
                    "id": "call_1",
                    "name": "edit_chapter",
                    "args": {"chapter_ref": {"type": "order", "value": 1}},
                }
            ],
            ensure_ascii=False,
        ),
    )

    compact = _compact_task_history_message(message, current_agent_name="writer")

    assert compact is not None
    assert compact["tool_calls"] == [
        {
            "id": "call_1",
            "name": "edit_chapter",
            "args": {"chapter_ref": {"type": "order", "value": 1}},
        }
    ]


def test_compact_tool_message_drops_verbose_data() -> None:
    message = TaskMessage(
        task_id="task-1",
        role="tool",
        content=json.dumps(
            {
                "success": True,
                "message": "Kerangka bab telah ditulis",
                "data": {"beats": [{"content": "Tokoh utama berangkat -> tiba di lokasi"}]},
                "metadata": {"tool_name": "confirm_outline"},
            },
            ensure_ascii=False,
        ),
        tool_call_id="call_1",
    )

    compact = _compact_task_history_message(message)

    assert compact == {
        "role": "tool",
        "tool_call_id": "call_1",
        "tool_name": "confirm_outline",
        "success": True,
        "message": "Kerangka bab telah ditulis",
    }
    assert "data" not in compact


def test_compact_tool_message_filters_other_agent_result() -> None:
    message = TaskMessage(
        task_id="task-1",
        role="tool",
        agent_id="designer",
        content=json.dumps(
            {
                "success": True,
                "message": "Kerangka bab telah ditulis",
                "data": {"beats": [{"content": "Tokoh utama berangkat -> tiba di lokasi"}]},
                "metadata": {"tool_name": "confirm_outline"},
            },
            ensure_ascii=False,
        ),
        tool_call_id="call_1",
    )

    compact = _compact_task_history_message(message, current_agent_name="writer")

    assert compact == {
        "role": "assistant",
        "content": "<agent_role>designer</agent_role>\nKonteks hasil tool: confirm_outline - Kerangka bab telah ditulis",
        "agent_id": "designer",
    }


def test_compact_task_history_drops_reasoning_messages() -> None:
    messages = [
        TaskMessage(
            task_id="task-1",
            role="assistant",
            content="Penalaran lama",
            message_type="reasoning",
            message_metadata='{"event_type": "reasoning"}',
        ),
        TaskMessage(
            task_id="task-1",
            role="assistant",
            content="Jawaban resmi",
            message_type="text",
        ),
        TaskMessage(
            task_id="task-1",
            role="assistant",
            content="Penalaran terbaru",
            message_type="reasoning",
            message_metadata='{"event_type": "reasoning"}',
        ),
    ]

    compact = _compact_task_history(messages)

    assert [message["content"] for message in compact] == ["Jawaban resmi"]


def test_compact_task_history_drops_hidden_and_node_messages() -> None:
    messages = [
        TaskMessage(
            task_id="task-1",
            role="system",
            content="",
            message_type="node_start",
            display_channel="hidden",
        ),
        TaskMessage(
            task_id="task-1",
            role="system",
            content="Status internal",
            message_type="text",
            display_channel="hidden",
        ),
        TaskMessage(
            task_id="task-1",
            role="assistant",
            content="Jawaban resmi",
            message_type="text",
        ),
    ]

    compact = _compact_task_history(messages)

    assert [message["content"] for message in compact] == ["Jawaban resmi"]


def test_compact_task_history_drops_unanswered_assistant_tool_call() -> None:
    messages = [
        TaskMessage(
            task_id="task-1",
            role="assistant",
            agent_id="writer",
            content="Bersiap menyunting bab",
            tool_calls=json.dumps(
                [{"id": "call-edit", "name": "edit_chapter", "args": {"content": "new"}}],
                ensure_ascii=False,
            ),
        )
    ]

    assert _compact_task_history(messages, current_agent_name="writer") == []


def test_compact_task_history_keeps_answered_assistant_tool_call_pair() -> None:
    messages = [
        TaskMessage(
            task_id="task-1",
            role="assistant",
            agent_id="writer",
            content="Bersiap membaca bab",
            tool_calls=json.dumps(
                [{"id": "call-read", "name": "read_chapter", "args": {"chapter_ref": {"type": "order", "value": 1}}}],
                ensure_ascii=False,
            ),
        ),
        TaskMessage(
            task_id="task-1",
            role="tool",
            agent_id="writer",
            content=json.dumps(
                {"success": True, "message": "Isi bab berhasil diambil", "metadata": {"tool_name": "read_chapter"}},
                ensure_ascii=False,
            ),
            tool_call_id="call-read",
        ),
    ]

    compact = _compact_task_history(messages, current_agent_name="writer")

    assert [message["role"] for message in compact] == ["assistant", "tool"]


def test_compact_task_history_drops_clarification_panel_between_tool_pair() -> None:
    messages = [
        TaskMessage(
            task_id="task-1",
            role="assistant",
            agent_id="explore",
            content="Ide Anda sudah jelas, saya masih perlu memastikan beberapa detail:",
            tool_calls=json.dumps(
                [{"id": "call-ask", "name": "ask_user", "args": {"questions": []}}],
                ensure_ascii=False,
            ),
        ),
        TaskMessage(
            task_id="task-1",
            role="assistant",
            agent_id="explore",
            content="Perlu klarifikasi: setelah berpindah dunia, dunia seperti apa yang dimasuki?",
            message_metadata=json.dumps({"event_type": "clarification"}, ensure_ascii=False),
        ),
        TaskMessage(
            task_id="task-1",
            role="tool",
            agent_id="explore",
            content=json.dumps(
                {
                    "success": True,
                    "message": "Pengguna sudah menjawab",
                    "metadata": {"tool_name": "ask_user"},
                },
                ensure_ascii=False,
            ),
            tool_call_id="call-ask",
        ),
    ]

    compact = _compact_task_history(messages, current_agent_name="explore")

    assert [message["role"] for message in compact] == ["assistant", "tool"]
    assert compact[0]["tool_calls"][0]["id"] == "call-ask"
    assert compact[1]["tool_call_id"] == "call-ask"


def test_compact_task_history_drops_tool_approval_message_between_tool_pair() -> None:
    messages = [
        TaskMessage(
            task_id="task-1",
            role="assistant",
            agent_id="writer",
            content="Buat bab",
            tool_calls=json.dumps(
                [
                    {
                        "id": "call-create",
                        "name": "create_chapter",
                        "args": {"chapter_ref": {"type": "order", "value": 99}},
                    }
                ],
                ensure_ascii=False,
            ),
        ),
        TaskMessage(
            task_id="task-1",
            role="assistant",
            agent_id="writer",
            content="Tool ini memerlukan izin pengguna.",
            message_type="approval",
            message_metadata=json.dumps(
                {"event_type": "tool_approval_required"},
                ensure_ascii=False,
            ),
        ),
        TaskMessage(
            task_id="task-1",
            role="tool",
            agent_id="writer",
            content=json.dumps(
                {
                    "success": True,
                    "message": "Bab berhasil dibuat",
                    "metadata": {"tool_name": "create_chapter"},
                },
                ensure_ascii=False,
            ),
            tool_call_id="call-create",
        ),
    ]

    compact = _compact_task_history(messages, current_agent_name="writer")

    assert len(compact) == 2
    assert compact[0]["role"] == "assistant"
    assert compact[0]["tool_calls"][0]["id"] == "call-create"
    assert compact[1]["role"] == "tool"
    assert compact[1]["tool_call_id"] == "call-create"
    assert all("Perlu klarifikasi" not in str(message.get("content") or "") for message in compact)


async def test_build_chat_messages_injects_handoff_without_task_history(monkeypatch) -> None:
    version = type(
        "Version",
        (),
        {
            "entries": [
                type(
                    "Entry",
                    (),
                    {"role": "system", "content": "Prompt sistem", "order_index": 0, "is_enabled": True},
                )()
            ]
        },
    )()
    monkeypatch.setattr(
        prompt_chain_runner.prompt_chain_service,
        "get_latest_version_with_entries_or_default",
        AsyncMock(return_value=version),
    )

    class FakeCompiler:
        def __init__(self) -> None:
            self.compile_calls: list[dict[str, object]] = []

        async def compile(self, *, entries):
            self.compile_calls.append(
                {
                    "entries": entries,
                }
            )
            return type("CompileResult", (), {"entries": entries})()

    compiler = FakeCompiler()
    monkeypatch.setattr(prompt_chain_runner, "PromptChainCompiler", lambda: compiler)

    messages = await build_chat_messages(
        AsyncMock(),
        prompt_id="builtin-agent--writer",
        runtime=ChatRuntime(
            current_message="Permintaan penulisan",
            anchor_chapter_id="chapter-7",
            skill_messages=[{"role": "system", "content": "<skill>Konteks skill</skill>"}],
            handoff_messages=[{"role": "user", "content": "<workflow_handoff>Hanya serahkan artefak</workflow_handoff>"}],
        ),
    )

    assert [message["content"] for message in messages] == [
        "Prompt sistem",
        "<skill>Konteks skill</skill>",
        "<workflow_handoff>Hanya serahkan artefak</workflow_handoff>",
        "Permintaan penulisan",
    ]


async def test_build_chat_messages_merges_consecutive_system_messages_when_enabled(
    monkeypatch,
) -> None:
    version = type(
        "Version",
        (),
        {
            "entries": [
                type(
                    "Entry",
                    (),
                    {"role": "system", "content": "Prompt sistem satu", "order_index": 0, "is_enabled": True},
                )(),
                type(
                    "Entry",
                    (),
                    {"role": "system", "content": "Prompt sistem dua", "order_index": 1, "is_enabled": True},
                )(),
            ]
        },
    )()
    monkeypatch.setattr(
        prompt_chain_runner.prompt_chain_service,
        "get_latest_version_with_entries_or_default",
        AsyncMock(return_value=version),
    )

    class FakeCompiler:
        async def compile(self, *, entries):
            return type("CompileResult", (), {"entries": entries})()

    monkeypatch.setattr(prompt_chain_runner, "PromptChainCompiler", lambda: FakeCompiler())

    with patch(
        "app.agent_runtime.context.processors.compress.setting_repo.get_by_key",
        new=AsyncMock(
            return_value=SimpleNamespace(key="compress_system_prompts", value="true")
        ),
    ):
        messages = await build_chat_messages(
            AsyncMock(),
            prompt_id="session-title",
            runtime=ChatRuntime(current_message="Tulis satu bagian"),
        )

    assert messages == [
        {"role": "system", "content": "Prompt sistem satu\n\nPrompt sistem dua"},
        {"role": "user", "content": "Tulis satu bagian"},
    ]


async def test_build_chat_messages_does_not_append_empty_current_message(monkeypatch) -> None:
    version = type(
        "Version",
        (),
        {
            "entries": [
                type(
                    "Entry",
                    (),
                    {"role": "system", "content": "Prompt sistem", "order_index": 0, "is_enabled": True},
                )()
            ]
        },
    )()
    monkeypatch.setattr(
        prompt_chain_runner.prompt_chain_service,
        "get_latest_version_with_entries_or_default",
        AsyncMock(return_value=version),
    )

    class FakeCompiler:
        async def compile(self, *, entries):
            return type("CompileResult", (), {"entries": entries})()

    monkeypatch.setattr(prompt_chain_runner, "PromptChainCompiler", FakeCompiler)

    messages = await build_chat_messages(
        AsyncMock(),
        prompt_id="builtin-agent--writer",
        runtime=ChatRuntime(
            current_message="",
            handoff_messages=[{"role": "user", "content": "<workflow_handoff>Memuat permintaan awal</workflow_handoff>"}],
        ),
    )

    assert [message["content"] for message in messages] == [
        "Prompt sistem",
        "<workflow_handoff>Memuat permintaan awal</workflow_handoff>",
    ]


async def test_build_chat_messages_appends_current_agent_local_react_history(monkeypatch) -> None:
    version = type(
        "Version",
        (),
        {
            "entries": [
                type(
                    "Entry",
                    (),
                    {"role": "system", "content": "Prompt sistem", "order_index": 0, "is_enabled": True},
                )()
            ]
        },
    )()
    monkeypatch.setattr(
        prompt_chain_runner.prompt_chain_service,
        "get_latest_version_with_entries_or_default",
        AsyncMock(return_value=version),
    )

    class FakeCompiler:
        async def compile(self, *, entries):
            return type("CompileResult", (), {"entries": entries})()

    task_messages = [
        TaskMessage(
            task_id="task-1",
            role="assistant",
            agent_id="writer",
            content="Bersiap membaca bab",
            tool_calls=json.dumps(
                [{"id": "call-1", "name": "read_chapter", "args": {"chapter_ref": {"type": "order", "value": 1}}}],
                ensure_ascii=False,
            ),
            message_metadata=json.dumps({"event_type": "assistant_message", "revision_id": "revision-1"}),
        ),
        TaskMessage(
            task_id="task-1",
            role="tool",
            agent_id="writer",
            content=json.dumps(
                {"success": True, "message": "Sudah dibaca", "metadata": {"tool_name": "read_chapter"}},
                ensure_ascii=False,
            ),
            tool_call_id="call-1",
            message_metadata=json.dumps({"event_type": "tool_result", "revision_id": "revision-1"}),
        ),
        TaskMessage(
            task_id="task-1",
            role="assistant",
            agent_id="designer",
            content="Riwayat Agent lain tidak boleh masuk",
            message_metadata=json.dumps({"event_type": "assistant_message", "revision_id": "revision-1"}),
        ),
        TaskMessage(
            task_id="task-1",
            role="assistant",
            agent_id="writer",
            content="revision lama tidak boleh masuk",
            message_metadata=json.dumps({"event_type": "assistant_message", "revision_id": "revision-0"}),
        ),
    ]
    monkeypatch.setattr(prompt_chain_runner, "PromptChainCompiler", FakeCompiler)
    monkeypatch.setattr(
        prompt_chain_runner.task_message_repo,
        "list_by_task",
        AsyncMock(return_value=task_messages),
    )

    messages = await build_chat_messages(
        AsyncMock(),
        prompt_id="builtin-agent--writer",
        runtime=ChatRuntime(
            current_message="Lanjutkan menulis",
            task_id="task-1",
            history_agent_name="writer",
            history_revision_id="revision-1",
            handoff_messages=[{"role": "user", "content": "<workflow_handoff>Kerangka</workflow_handoff>"}],
        ),
    )

    contents = [str(message.get("content") or "") for message in messages]
    assert contents[:2] == ["Prompt sistem", "<workflow_handoff>Kerangka</workflow_handoff>"]
    assert messages[2]["role"] == "assistant"
    assert messages[2]["content"] == "Bersiap membaca bab"
    assert messages[3]["role"] == "tool"
    assert messages[3]["tool_call_id"] == "call-1"
    assert messages[3]["message"] == "Sudah dibaca"
    assert contents[-1] == "Lanjutkan menulis"
    assert any(message.get("role") == "tool" and message.get("tool_call_id") == "call-1" for message in messages)
    assert "Riwayat Agent lain tidak boleh masuk" not in contents
    assert "revision lama tidak boleh masuk" not in contents


async def test_build_chat_messages_places_writer_history_before_new_user_message(monkeypatch) -> None:
    version = type(
        "Version",
        (),
        {
            "entries": [
                type(
                    "Entry",
                    (),
                    {"role": "system", "content": "Prompt sistem", "order_index": 0, "is_enabled": True},
                )()
            ]
        },
    )()
    monkeypatch.setattr(
        prompt_chain_runner.prompt_chain_service,
        "get_latest_version_with_entries_or_default",
        AsyncMock(return_value=version),
    )

    class FakeCompiler:
        async def compile(self, *, entries):
            return type("CompileResult", (), {"entries": entries})()

    task_messages = [
        TaskMessage(
            task_id="task-1",
            role="assistant",
            agent_id="writer",
            content="Bersiap menyunting bab",
            tool_calls=json.dumps(
                [
                    {
                        "id": "call-edit",
                        "name": "edit_chapter",
                        "args": {"chapter_ref": {"type": "order", "value": 1}},
                    }
                ],
                ensure_ascii=False,
            ),
            message_metadata=json.dumps({"event_type": "assistant_message", "revision_id": "revision-1"}),
        ),
        TaskMessage(
            task_id="task-1",
            role="tool",
            agent_id="writer",
            content=json.dumps(
                {"success": True, "message": "Sudah disunting", "metadata": {"tool_name": "edit_chapter"}},
                ensure_ascii=False,
            ),
            tool_call_id="call-edit",
            message_metadata=json.dumps({"event_type": "tool_result", "revision_id": "revision-1"}),
        ),
    ]
    monkeypatch.setattr(prompt_chain_runner, "PromptChainCompiler", FakeCompiler)
    monkeypatch.setattr(
        prompt_chain_runner.task_message_repo,
        "list_by_task",
        AsyncMock(return_value=task_messages),
    )

    messages = await build_chat_messages(
        AsyncMock(),
        prompt_id="builtin-agent--writer",
        runtime=ChatRuntime(
            current_message="Lanjutkan perbaikan sesuai masukan review",
            task_id="task-1",
            history_agent_name="writer",
            history_revision_id="revision-1",
            handoff_messages=[{"role": "user", "content": "<workflow_handoff>Review tidak lolos</workflow_handoff>"}],
        ),
    )

    assert [message.get("role") for message in messages] == [
        "system",
        "user",
        "assistant",
        "tool",
        "user",
    ]
    assert messages[-1]["content"] == "Lanjutkan perbaikan sesuai masukan review"
    assert messages[2].get("tool_calls") == [
        {
            "id": "call-edit",
            "name": "edit_chapter",
            "args": {"chapter_ref": {"type": "order", "value": 1}},
        }
    ]
    assert messages[3].get("tool_call_id") == "call-edit"
