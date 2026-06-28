# -*- coding: utf-8 -*-
"""Prompt chain runner history compaction tests."""

import json
from unittest.mock import AsyncMock

from app.memory import prompt_chain_runner
from app.memory.prompt_chain_runner import ChatRuntime, _compact_task_history, _compact_task_history_message, build_chat_messages
from app.storage.models.task_message import TaskMessage


def test_compact_assistant_tool_calls_preserves_tool_input() -> None:
    message = TaskMessage(
        task_id="task-1",
        role="assistant",
        agent_id="designer",
        content="我将写入大纲",
        tool_calls=json.dumps(
            [
                {
                    "id": "call_1",
                    "name": "confirm_outline",
                    "args": {"beats": [{"content": "主角出发→抵达现场"}]},
                }
            ],
            ensure_ascii=False,
        ),
    )

    compact = _compact_task_history_message(message)

    assert compact == {
        "role": "assistant",
        "content": "我将写入大纲",
        "agent_id": "designer",
        "tool_calls": [
            {
                "id": "call_1",
                "name": "confirm_outline",
                "args": {"beats": [{"content": "主角出发→抵达现场"}]},
            }
        ],
    }


def test_compact_assistant_tool_calls_filters_other_agent_tools() -> None:
    message = TaskMessage(
        task_id="task-1",
        role="assistant",
        agent_id="designer",
        content="大纲已确认，现在开始写作。",
        tool_calls=json.dumps(
            [
                {
                    "id": "call_1",
                    "name": "confirm_outline",
                    "args": {"beats": [{"content": "主角出发→抵达现场"}]},
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
    assert "不可作为当前Agent可用工具" in compact["content"]
    assert "confirm_outline" in compact["content"]


def test_compact_assistant_tool_calls_keeps_current_agent_tools() -> None:
    message = TaskMessage(
        task_id="task-1",
        role="assistant",
        agent_id="writer",
        content="准备编辑章节。",
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
                "message": "章节大纲已写入",
                "data": {"beats": [{"content": "主角出发→抵达现场"}]},
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
        "message": "章节大纲已写入",
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
                "message": "章节大纲已写入",
                "data": {"beats": [{"content": "主角出发→抵达现场"}]},
                "metadata": {"tool_name": "confirm_outline"},
            },
            ensure_ascii=False,
        ),
        tool_call_id="call_1",
    )

    compact = _compact_task_history_message(message, current_agent_name="writer")

    assert compact == {
        "role": "assistant",
        "content": "<agent_role>designer</agent_role>\n工具结果上下文：confirm_outline - 章节大纲已写入",
        "agent_id": "designer",
    }


def test_compact_task_history_drops_reasoning_messages() -> None:
    messages = [
        TaskMessage(
            task_id="task-1",
            role="assistant",
            content="旧思考",
            message_type="reasoning",
            message_metadata='{"event_type": "reasoning"}',
        ),
        TaskMessage(
            task_id="task-1",
            role="assistant",
            content="正式回答",
            message_type="text",
        ),
        TaskMessage(
            task_id="task-1",
            role="assistant",
            content="最新思考",
            message_type="reasoning",
            message_metadata='{"event_type": "reasoning"}',
        ),
    ]

    compact = _compact_task_history(messages)

    assert [message["content"] for message in compact] == ["正式回答"]


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
            content="内部状态",
            message_type="text",
            display_channel="hidden",
        ),
        TaskMessage(
            task_id="task-1",
            role="assistant",
            content="正式回答",
            message_type="text",
        ),
    ]

    compact = _compact_task_history(messages)

    assert [message["content"] for message in compact] == ["正式回答"]


def test_compact_task_history_drops_unanswered_assistant_tool_call() -> None:
    messages = [
        TaskMessage(
            task_id="task-1",
            role="assistant",
            agent_id="writer",
            content="准备编辑章节",
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
            content="准备读取章节",
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
                {"success": True, "message": "章节内容获取成功", "metadata": {"tool_name": "read_chapter"}},
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
            agent_id="explorer",
            content="你的想法很明确，我这边还需要确认几个细节：",
            tool_calls=json.dumps(
                [{"id": "call-ask", "name": "ask_user", "args": {"questions": []}}],
                ensure_ascii=False,
            ),
        ),
        TaskMessage(
            task_id="task-1",
            role="assistant",
            agent_id="explorer",
            content="需要澄清：穿越后进入什么样的世界？",
            message_metadata=json.dumps({"event_type": "clarification"}, ensure_ascii=False),
        ),
        TaskMessage(
            task_id="task-1",
            role="tool",
            agent_id="explorer",
            content=json.dumps(
                {
                    "success": True,
                    "message": "用户已回答",
                    "metadata": {"tool_name": "ask_user"},
                },
                ensure_ascii=False,
            ),
            tool_call_id="call-ask",
        ),
    ]

    compact = _compact_task_history(messages, current_agent_name="explorer")

    assert [message["role"] for message in compact] == ["assistant", "tool"]
    assert compact[0]["tool_calls"][0]["id"] == "call-ask"
    assert compact[1]["tool_call_id"] == "call-ask"


def test_compact_task_history_drops_tool_approval_message_between_tool_pair() -> None:
    messages = [
        TaskMessage(
            task_id="task-1",
            role="assistant",
            agent_id="writer",
            content="创建章节",
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
            content="该工具需要用户许可。",
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
                    "message": "章节创建成功",
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
    assert all("需要澄清" not in str(message.get("content") or "") for message in compact)


async def test_build_chat_messages_injects_handoff_without_task_history(monkeypatch) -> None:
    version = type(
        "Version",
        (),
        {
            "entries": [
                type(
                    "Entry",
                    (),
                    {"role": "system", "content": "系统提示", "order_index": 0, "is_enabled": True},
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
        def __init__(self, session) -> None:
            self.session = session
            self.compile_calls: list[dict[str, object]] = []

        async def compile(self, *, entries, project_id, chapter_id):
            self.compile_calls.append(
                {
                    "entries": entries,
                    "project_id": project_id,
                    "chapter_id": chapter_id,
                }
            )
            return type("CompileResult", (), {"entries": entries})()

    compiler = FakeCompiler(AsyncMock())
    monkeypatch.setattr(prompt_chain_runner, "PromptChainCompiler", lambda session: compiler)

    messages = await build_chat_messages(
        AsyncMock(),
        mode_name="assistant",
        task_name="agent",
        agent_name="writer",
        project_id="project-1",
        chapter_id="chapter-1",
        runtime=ChatRuntime(
            current_message="写作请求",
            anchor_chapter_id="chapter-7",
            skill_messages=[{"role": "system", "content": "<skill>技能上下文</skill>"}],
            handoff_messages=[{"role": "user", "content": "<workflow_handoff>只交接产物</workflow_handoff>"}],
        ),
    )

    assert compiler.compile_calls[0]["chapter_id"] == "chapter-7"
    assert [message["content"] for message in messages] == [
        "系统提示",
        "<skill>技能上下文</skill>",
        "<workflow_handoff>只交接产物</workflow_handoff>",
        "写作请求",
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
                    {"role": "system", "content": "系统提示", "order_index": 0, "is_enabled": True},
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
        def __init__(self, session) -> None:
            self.session = session

        async def compile(self, *, entries, project_id, chapter_id):
            return type("CompileResult", (), {"entries": entries})()

    monkeypatch.setattr(prompt_chain_runner, "PromptChainCompiler", FakeCompiler)

    messages = await build_chat_messages(
        AsyncMock(),
        mode_name="assistant",
        task_name="agent",
        agent_name="writer",
        project_id="project-1",
        chapter_id="chapter-1",
        runtime=ChatRuntime(
            current_message="",
            handoff_messages=[{"role": "user", "content": "<workflow_handoff>包含初始请求</workflow_handoff>"}],
        ),
    )

    assert [message["content"] for message in messages] == [
        "系统提示",
        "<workflow_handoff>包含初始请求</workflow_handoff>",
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
                    {"role": "system", "content": "系统提示", "order_index": 0, "is_enabled": True},
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
        def __init__(self, session) -> None:
            self.session = session

        async def compile(self, *, entries, project_id, chapter_id):
            return type("CompileResult", (), {"entries": entries})()

    task_messages = [
        TaskMessage(
            task_id="task-1",
            role="assistant",
            agent_id="writer",
            content="准备读取章节",
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
                {"success": True, "message": "已读取", "metadata": {"tool_name": "read_chapter"}},
                ensure_ascii=False,
            ),
            tool_call_id="call-1",
            message_metadata=json.dumps({"event_type": "tool_result", "revision_id": "revision-1"}),
        ),
        TaskMessage(
            task_id="task-1",
            role="assistant",
            agent_id="designer",
            content="其它 Agent 历史不应进入",
            message_metadata=json.dumps({"event_type": "assistant_message", "revision_id": "revision-1"}),
        ),
        TaskMessage(
            task_id="task-1",
            role="assistant",
            agent_id="writer",
            content="旧 revision 不应进入",
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
        mode_name="assistant",
        task_name="agent",
        agent_name="writer",
        project_id="project-1",
        chapter_id="chapter-1",
        runtime=ChatRuntime(
            current_message="继续写作",
            task_id="task-1",
            history_agent_name="writer",
            history_revision_id="revision-1",
            handoff_messages=[{"role": "user", "content": "<workflow_handoff>大纲</workflow_handoff>"}],
        ),
    )

    contents = [str(message.get("content") or "") for message in messages]
    assert contents[:2] == ["系统提示", "<workflow_handoff>大纲</workflow_handoff>"]
    assert messages[2]["role"] == "assistant"
    assert messages[2]["content"] == "准备读取章节"
    assert messages[3]["role"] == "tool"
    assert messages[3]["tool_call_id"] == "call-1"
    assert messages[3]["message"] == "已读取"
    assert contents[-1] == "继续写作"
    assert any(message.get("role") == "tool" and message.get("tool_call_id") == "call-1" for message in messages)
    assert "其它 Agent 历史不应进入" not in contents
    assert "旧 revision 不应进入" not in contents


async def test_build_chat_messages_places_writer_history_before_new_user_message(monkeypatch) -> None:
    version = type(
        "Version",
        (),
        {
            "entries": [
                type(
                    "Entry",
                    (),
                    {"role": "system", "content": "系统提示", "order_index": 0, "is_enabled": True},
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
        def __init__(self, session) -> None:
            self.session = session

        async def compile(self, *, entries, project_id, chapter_id):
            return type("CompileResult", (), {"entries": entries})()

    task_messages = [
        TaskMessage(
            task_id="task-1",
            role="assistant",
            agent_id="writer",
            content="准备编辑章节",
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
                {"success": True, "message": "已编辑", "metadata": {"tool_name": "edit_chapter"}},
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
        mode_name="assistant",
        task_name="agent",
        agent_name="writer",
        project_id="project-1",
        chapter_id="chapter-1",
        runtime=ChatRuntime(
            current_message="根据审查意见继续修改",
            task_id="task-1",
            history_agent_name="writer",
            history_revision_id="revision-1",
            handoff_messages=[{"role": "user", "content": "<workflow_handoff>审查未通过</workflow_handoff>"}],
        ),
    )

    assert [message.get("role") for message in messages] == [
        "system",
        "user",
        "assistant",
        "tool",
        "user",
    ]
    assert messages[-1]["content"] == "根据审查意见继续修改"
    assert messages[2].get("tool_calls") == [
        {
            "id": "call-edit",
            "name": "edit_chapter",
            "args": {"chapter_ref": {"type": "order", "value": 1}},
        }
    ]
    assert messages[3].get("tool_call_id") == "call-edit"
