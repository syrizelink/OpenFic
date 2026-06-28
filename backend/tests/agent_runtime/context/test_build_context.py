import json
from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from app.agent_runtime.context import ContextBuildError, build_context
from app.agent_runtime.persistence.errors import PersistenceLoadError
from app.agent_runtime.graph.state import AgentRuntimeState
from app.agent_runtime.persistence.compaction_types import PersistedCompaction
from app.agent_runtime.context.types import ContextMessage


@pytest.fixture
def base_state() -> AgentRuntimeState:
    return cast(AgentRuntimeState, {
        "session_id": "s1",
        "task_id": "t1",
        "project_id": "p1",
        "model_config": {"max_context_tokens": 8000},
        "active_agent": "writer",
        "is_completed": False,
        "error": None,
        "retry_count": 0,
        "user_request": "写一段",
        "installed_skill_ids": [],
        "current_revision_id": None,
    })


@pytest.mark.asyncio
async def test_missing_max_context_tokens_raises(base_state: AgentRuntimeState) -> None:
    base_state["model_config"] = {}
    with pytest.raises(ContextBuildError) as exc:
        await build_context(
            state=base_state,
            agent_name="writer",
            node_messages=[],
            db_session=AsyncMock(),
        )
    assert exc.value.part == "config"


@pytest.mark.asyncio
async def test_assembles_messages_in_order(base_state: AgentRuntimeState) -> None:
    sys_msgs = [
        ContextMessage(role="system", content="sys", metadata={"part": "system_prompt"}),
        ContextMessage(role="user", content="prompt-user", metadata={"part": "system_prompt"}),
        ContextMessage(role="assistant", content="prompt-assistant", metadata={"part": "system_prompt"}),
    ]

    with (
        patch(
            "app.agent_runtime.context.build_context.build_system_prompt",
            new=AsyncMock(return_value=sys_msgs),
        ), patch(
            "app.agent_runtime.context.build_context.build_rules",
            new=AsyncMock(return_value=None),
        ), patch(
            "app.agent_runtime.context.build_context.build_skills",
            new=AsyncMock(return_value=None),
        ), patch(
            "app.agent_runtime.context.build_context.compaction_repo.list_by_session",
            new=AsyncMock(return_value=[]),
        ),
    ):
        out = await build_context(
            state=base_state,
            agent_name="writer",
            node_messages=[{"role": "user", "content": "hi", "metadata": {"part": "history"}}],
            db_session=AsyncMock(),
        )

    assert isinstance(out[0], SystemMessage)
    assert out[0].content == "sys"
    assert isinstance(out[1], HumanMessage)
    assert out[1].content == "prompt-user"
    assert out[2].type == "ai"
    assert out[2].content == "prompt-assistant"
    assert isinstance(out[-1], HumanMessage)
    assert out[-1].content == "hi"


@pytest.mark.asyncio
async def test_build_context_applies_persisted_compaction_overlay_to_history_only(
    base_state: AgentRuntimeState,
) -> None:
    compaction = PersistedCompaction(
        id="compaction-1",
        session_id="s1",
        task_id="t1",
        project_id="p1",
        start_seq=1,
        end_seq=2,
        summary="旧内容摘要",
        trigger="auto",
        source_input_tokens=100,
        summary_tokens=10,
        created_at=datetime.now(UTC),
    )

    with (
        patch(
            "app.agent_runtime.context.build_context.build_system_prompt",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.agent_runtime.context.build_context.build_rules",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.agent_runtime.context.build_context.build_skills",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.agent_runtime.context.build_context.compaction_repo.list_by_session",
            new=AsyncMock(return_value=[compaction]),
        ),
    ):
        out = await build_context(
            state=base_state,
            agent_name="writer",
            node_messages=[
                {"role": "user", "content": "首轮", "metadata": {"seq": 0}},
                {"role": "assistant", "content": "旧 A", "metadata": {"seq": 1}},
                {"role": "user", "content": "旧 B", "metadata": {"seq": 2}},
                {"role": "assistant", "content": "最新", "metadata": {"seq": 3}},
            ],
            db_session=AsyncMock(),
        )

    assert [m.content for m in out] == [
        "首轮",
        "<compaction-summary>\n旧内容摘要\n</compaction-summary>",
        "最新",
    ]


@pytest.mark.asyncio
async def test_build_context_wraps_compaction_load_errors(
    base_state: AgentRuntimeState,
) -> None:
    cause = PersistenceLoadError("boom")

    with (
        patch(
            "app.agent_runtime.context.build_context.build_system_prompt",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.agent_runtime.context.build_context.build_rules",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.agent_runtime.context.build_context.build_skills",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.agent_runtime.context.build_context.compaction_repo.list_by_session",
            new=AsyncMock(side_effect=cause),
        ),
    ):
        with pytest.raises(ContextBuildError) as exc:
            await build_context(
                state=base_state,
                agent_name="writer",
                node_messages=[],
                db_session=AsyncMock(),
            )

    assert exc.value.part == "compaction"
    assert exc.value.cause is cause


@pytest.mark.asyncio
async def test_compacts_chapter_write_tool_result_for_live_llm_context(
    base_state: AgentRuntimeState,
) -> None:
    with (
        patch(
            "app.agent_runtime.context.build_context.build_system_prompt",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.agent_runtime.context.build_context.build_rules",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.agent_runtime.context.build_context.build_skills",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.agent_runtime.context.build_context.compaction_repo.list_by_session",
            new=AsyncMock(return_value=[]),
        ),
    ):
        out = await build_context(
            state=base_state,
            agent_name="writer",
            node_messages=[
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "name": "write_chapter",
                            "args": {"title": "第一章", "content": "正文"},
                        }
                    ],
                },
                {
                    "role": "tool",
                    "content": json.dumps(
                        {
                            "type": "ok",
                            "success": True,
                            "tool_name": "write_chapter",
                            "revision_id": "rev-1",
                            "word_count": 2,
                            "chapter": {
                                "id": "chap-1",
                                "title": "第一章",
                                "content": "正文",
                            },
                            "chapter_diff": {
                                "operation": "create",
                                "sections": [],
                            },
                            "affected_chapters": ["chap-1"],
                            "message": "章节已写入",
                        },
                        ensure_ascii=False,
                    ),
                    "tool_call_id": "call_1",
                },
            ],
            db_session=AsyncMock(),
        )

    assert isinstance(out[-1], ToolMessage)
    tool_content = out[-1].content
    assert isinstance(tool_content, str)
    assert json.loads(tool_content) == {
        "success": True,
        "tool_name": "write_chapter",
        "word_count": 2,
        "message": "章节已写入",
    }
