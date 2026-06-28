from collections.abc import AsyncGenerator
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.agent_runtime.context.compaction.service import (
    CompactionError,
    compact_window,
)
from app.agent_runtime.context.compaction.window import CompactionWindow
from app.agent_runtime.context.types import ContextMessage
from app.agent_runtime.graph.state import AgentRuntimeState
from app.agent_runtime.persistence import compaction_repo
from app.agent_runtime.persistence import repo as message_repo
from app.agent_runtime.persistence.model import AgentContextCompaction, AgentRunMessage
from app.agent_runtime.runner.session_runner import SessionRunner
from app.storage.models.chapter import Chapter
from app.storage.models.project import Project
from app.storage.models.task import Task
from app.storage.models.volume import Volume


def _ai_message(
    content: str,
    usage_metadata: dict[str, Any] | None = None,
) -> AIMessage:
    message = AIMessage(content=content)
    if usage_metadata is not None:
        object.__setattr__(message, "usage_metadata", cast(Any, usage_metadata))
    return message


def _table(model: Any) -> Any:
    return getattr(model, "__table__")


_TABLES = [
    _table(Project),
    _table(Volume),
    _table(Chapter),
    _table(Task),
    _table(AgentContextCompaction),
    _table(AgentRunMessage),
]


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all, tables=_TABLES)

    factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )
    async with factory() as session:
        project = Project(id="proj_test", title="测试项目")
        volume = Volume(
            id="vol_test",
            project_id="proj_test",
            title="第一卷",
            order=1,
            chapter_count=1,
        )
        chapter = Chapter(
            id="chap_test",
            project_id="proj_test",
            volume_id="vol_test",
            title="测试章节",
            order=1,
        )
        task = Task(
            id="task_test",
            project_id="proj_test",
            title="测试任务",
            mode="agent",
            agent_session_id="session_test",
        )
        session.add(project)
        session.add(volume)
        session.add(chapter)
        session.add(task)
        await session.commit()
        yield session

    await engine.dispose()


@pytest.fixture
def state() -> AgentRuntimeState:
    return {
        "session_id": "session_test",
        "task_id": "task_test",
        "project_id": "proj_test",
        "model_config": {
            "provider_type": "openai",
            "base_url": "",
            "api_key": "test-key",
            "model_id": "gpt-test",
            "max_context_tokens": 100_000,
            "temperature": 0.2,
            "max_tokens": 2048,
        },
        "active_agent": None,
        "is_completed": False,
        "error": None,
        "retry_count": 0,
        "user_request": "请继续",
        "installed_skill_ids": [],
        "current_revision_id": None,
    }


@pytest.fixture
def window() -> CompactionWindow:
    return CompactionWindow(
        start_seq=2,
        end_seq=5,
        messages=[ContextMessage(role="assistant", content="old")],
        source_input_tokens=321,
        transcript="<assistant>old</assistant>",
    )


class FakeModel:
    def __init__(self, response: AIMessage | Exception) -> None:
        self.response = response
        self.messages: list[Any] | None = None

    async def ainvoke(self, messages: list[Any]) -> AIMessage:
        self.messages = messages
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _prompt_version() -> SimpleNamespace:
    return SimpleNamespace(
        version=SimpleNamespace(id="v1"),
        entries=[
            SimpleNamespace(
                role="system",
                content="请压缩 transcript",
                order_index=0,
                is_enabled=True,
            ),
            SimpleNamespace(
                role="system",
                content="disabled",
                order_index=1,
                is_enabled=False,
            ),
        ],
    )


async def _record_event(
    events: list[tuple[str, dict[str, Any]]],
    name: str,
    payload: dict[str, Any],
) -> None:
    events.append((name, payload))


@pytest.mark.asyncio
async def test_compact_window_persists_raw_summary_and_emits_events_and_usage(
    db_session: AsyncSession,
    state: AgentRuntimeState,
    window: CompactionWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_model = FakeModel(
        _ai_message(
            "  摘要正文  ",
            {"input_tokens": 100, "output_tokens": 20},
        ),
    )
    events: list[tuple[str, dict[str, Any]]] = []
    usage_events: list[dict[str, Any]] = []

    monkeypatch.setattr(
        "app.agent_runtime.context.compaction.service.create_chat_model",
        lambda _config: fake_model,
    )
    monkeypatch.setattr(
        "app.agent_runtime.context.compaction.service.prompt_chain_service.get_latest_version_with_entries_or_default",
        AsyncMock(return_value=_prompt_version()),
    )

    result = await compact_window(
        db_session,
        state=state,
        window=window,
        trigger="manual",
        event_sink=lambda name, payload: _record_event(events, name, payload),
        usage_sink=usage_events.append,
    )

    assert result.summary == "摘要正文"
    assert result.start_seq == window.start_seq
    assert result.end_seq == window.end_seq
    assert fake_model.messages is not None
    assert isinstance(fake_model.messages[0], SystemMessage)
    assert isinstance(fake_model.messages[-1], HumanMessage)
    assert fake_model.messages[-1].content == window.transcript
    assert events[0][0] == "agent:compaction_start"
    assert events[-1][0] == "agent:compaction_success"
    assert "summary" not in events[-1][1]
    assert usage_events[0]["usage_kind"] == "compaction"
    assert usage_events[0]["usage"]["input_tokens"] == 100
    assert usage_events[0]["usage"]["output_tokens"] == 20
    normalized_usage = SessionRunner(
        session_id=state["session_id"],
        task_id=state["task_id"],
        model_config=state["model_config"],
        project_id=state["project_id"],
    )._normalize_usage_event(usage_events[0])
    assert normalized_usage["token_input"] == 100
    assert normalized_usage["token_output"] == 20

    rows = await compaction_repo.list_by_session(db_session, state["session_id"])
    assert [row.summary for row in rows] == ["摘要正文"]
    assert "<compaction-summary>" not in rows[0].summary

    display_rows = await message_repo.list_by_session(
        db_session,
        state["session_id"],
    )
    assert len(display_rows) == 1
    assert display_rows[0].id == f"compaction:{result.id}"
    assert display_rows[0].role == "system"
    assert display_rows[0].status == "complete"
    assert display_rows[0].content == "已进行压缩"
    assert display_rows[0].message_type == "compaction"
    assert display_rows[0].display_channel == "list"
    assert display_rows[0].llm_visibility == "hidden"
    assert display_rows[0].metadata == {
        "kind": "compaction",
        "compaction_id": result.id,
        "trigger": "manual",
    }


@pytest.mark.asyncio
async def test_compact_window_rejects_empty_summary_without_persisting(
    db_session: AsyncSession,
    state: AgentRuntimeState,
    window: CompactionWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_model = FakeModel(AIMessage(content=" \n\t "))
    events: list[tuple[str, dict[str, Any]]] = []

    monkeypatch.setattr(
        "app.agent_runtime.context.compaction.service.create_chat_model",
        lambda _config: fake_model,
    )
    monkeypatch.setattr(
        "app.agent_runtime.context.compaction.service.prompt_chain_service.get_latest_version_with_entries_or_default",
        AsyncMock(return_value=_prompt_version()),
    )

    with pytest.raises(CompactionError) as exc_info:
        await compact_window(
            db_session,
            state=state,
            window=window,
            trigger="auto",
            event_sink=lambda name, payload: _record_event(events, name, payload),
        )

    assert exc_info.value.code == "compaction_empty_summary"
    assert events[-1][0] == "agent:compaction_error"
    assert events[-1][1]["code"] == "compaction_empty_summary"
    rows = await compaction_repo.list_by_session(db_session, state["session_id"])
    assert rows == []


@pytest.mark.asyncio
async def test_compact_window_ignores_post_commit_sink_failures(
    db_session: AsyncSession,
    state: AgentRuntimeState,
    window: CompactionWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_model = FakeModel(
        _ai_message(
            "摘要正文",
            {"input_tokens": 100, "output_tokens": 20},
        ),
    )

    monkeypatch.setattr(
        "app.agent_runtime.context.compaction.service.create_chat_model",
        lambda _config: fake_model,
    )
    monkeypatch.setattr(
        "app.agent_runtime.context.compaction.service.prompt_chain_service.get_latest_version_with_entries_or_default",
        AsyncMock(return_value=_prompt_version()),
    )

    def event_sink(name: str, _payload: dict[str, Any]) -> None:
        if name == "agent:compaction_success":
            raise RuntimeError("success sink failed")

    def usage_sink(_payload: dict[str, Any]) -> None:
        raise RuntimeError("usage sink failed")

    result = await compact_window(
        db_session,
        state=state,
        window=window,
        trigger="manual",
        event_sink=event_sink,
        usage_sink=usage_sink,
    )

    assert result.summary == "摘要正文"
    rows = await compaction_repo.list_by_session(db_session, state["session_id"])
    assert [row.id for row in rows] == [result.id]


@pytest.mark.asyncio
async def test_compact_window_converts_llm_error_to_stable_error_event(
    db_session: AsyncSession,
    state: AgentRuntimeState,
    window: CompactionWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_model = FakeModel(RuntimeError("provider leaked transcript old stack"))
    events: list[tuple[str, dict[str, Any]]] = []

    monkeypatch.setattr(
        "app.agent_runtime.context.compaction.service.create_chat_model",
        lambda _config: fake_model,
    )
    monkeypatch.setattr(
        "app.agent_runtime.context.compaction.service.prompt_chain_service.get_latest_version_with_entries_or_default",
        AsyncMock(return_value=_prompt_version()),
    )

    with pytest.raises(CompactionError) as exc_info:
        await compact_window(
            db_session,
            state=state,
            window=window,
            trigger="manual",
            event_sink=lambda name, payload: _record_event(events, name, payload),
        )

    assert exc_info.value.code == "llm_error"
    assert events[-1][0] == "agent:compaction_error"
    error_payload = events[-1][1]
    assert error_payload["code"] == "llm_error"
    text = repr(error_payload)
    assert window.transcript not in text
    assert "provider" not in text
    assert "stack" not in text
    assert "summary" not in error_payload
    rows = await compaction_repo.list_by_session(db_session, state["session_id"])
    assert rows == []
