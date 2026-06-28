"""错误传播测试。"""

import pytest
from langchain_core.messages import AIMessageChunk

from app.agent_runtime.persistence.errors import (
    PersistenceLoadError,
    PersistenceWriteError,
)
from app.agent_runtime.persistence.loader import load_history
from app.agent_runtime.persistence.persister import MessagePersister


class _BrokenSession:
    async def execute(self, *_a, **_kw):
        raise RuntimeError("DB down")

    async def commit(self):
        raise RuntimeError("DB down")

    async def rollback(self):
        return None

    async def close(self):
        return None

    def add(self, *_a, **_kw):
        return None

    async def get(self, *_a, **_kw):
        raise RuntimeError("DB down")

    async def refresh(self, *_a, **_kw):
        return None


@pytest.mark.asyncio
async def test_load_history_propagates_load_error():
    with pytest.raises(PersistenceLoadError):
        await load_history(_BrokenSession(), "session_a")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_persister_write_failure_raises_write_error(sample_task):
    def make_session():
        return _BrokenSession()

    p = MessagePersister(
        session_id="s",
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        db_session_factory=make_session,
    )
    await p.handle({"event": "on_chat_model_start", "data": {}})
    await p.handle({
        "event": "on_chat_model_stream",
        "data": {"chunk": AIMessageChunk(content="hi")},
    })

    with pytest.raises(PersistenceWriteError):
        await p.handle({"event": "on_chat_model_end", "data": {}})


@pytest.mark.asyncio
async def test_persister_finalize_failure_raises_write_error(sample_task):
    def make_session():
        return _BrokenSession()

    p = MessagePersister(
        session_id="s",
        task_id=sample_task.id,
        project_id=sample_task.project_id,
        db_session_factory=make_session,
    )
    await p.handle({"event": "on_chat_model_start", "data": {}})
    await p.handle({
        "event": "on_chat_model_stream",
        "data": {"chunk": AIMessageChunk(content="half")},
    })
    with pytest.raises(PersistenceWriteError):
        await p.finalize(reason="cancelled")
