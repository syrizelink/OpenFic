"""Real CRDT + Agent + SQL integration without any Node runtime or child process."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from pycrdt import create_update_message, handle_sync_message, XmlFragment, XmlText
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.collaboration import service
from app.collaboration.document import clone_document, text_of, replace_exact
from app.storage.models.chapter import Chapter
from app.storage.models.project import Project
from app.storage.models.volume import Volume
from app.storage.models.task import Task
from app.storage.models.revision import Revision
from app.storage.repos import setting_repo, commit_repo


@pytest_asyncio.fixture
async def collaboration(tmp_path, monkeypatch):
    from app.agent_runtime.tools.impls.chapter import edit_chapter as tool_module
    from app.storage import database
    from app import settings as settings_module
    from tests.model_registry import register_sqlmodel_models

    register_sqlmodel_models()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/collaboration.db")
    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def new_session():
        return factory()

    monkeypatch.setattr(database, "create_session", new_session)
    monkeypatch.setattr(tool_module, "create_session", new_session)
    monkeypatch.setattr(settings_module, "BACKEND_DATA_DIR", tmp_path)
    # A regression back to a Node sidecar must fail even when Node is installed.
    monkeypatch.setattr(
        asyncio,
        "create_subprocess_exec",
        AsyncMock(side_effect=AssertionError("No subprocess permitted")),
    )
    hub = service.CollaborationHub()
    monkeypatch.setattr(service, "hub", hub)
    try:
        await hub.resume()
        async with factory() as session:
            project = Project(title="Collaboration")
            session.add(project)
            await session.flush()
            volume = Volume(project_id=project.id, title="Volume", order=1)
            session.add(volume)
            await session.flush()
            chapter = Chapter(
                project_id=project.id,
                volume_id=volume.id,
                title="Chapter",
                content="Sunny morning\nThe end",
                order=1,
            )
            task = Task(
                project_id=project.id,
                title="Edit",
                mode="agent",
                agent_session_id="session",
            )
            session.add(chapter)
            session.add(task)
            await session.flush()
            revision = Revision(
                project_id=project.id,
                task_id=task.id,
                message="edit",
                agent_session_id="session",
                user_message_seq=1,
                project_snapshot_title=project.title,
            )
            session.add(revision)
            await setting_repo.upsert(session, service.SETTING_KEY, "true")
            record = await service.document_record(session, chapter.id)
            name = service.room_for(record)
            room = hub.get_room(name, await service.load_document(session, name))
            await service.persist_document(
                session, hub.snapshot(name), record_activity=False
            )
            await session.commit()
        state = {
            "project_id": project.id,
            "session_id": "session",
            "task_id": task.id,
            "current_revision_id": revision.id,
        }
        yield SimpleNamespace(
            hub=hub,
            factory=factory,
            name=name,
            room=room,
            chapter=chapter,
            revision=revision,
            tool=tool_module.EditChapterTool(_state=state),
        )
    finally:
        await hub.stop()
        await engine.dispose()


class Socket:
    def __init__(self, collaboration):
        self.collaboration = collaboration
        self.messages = []

    async def send_bytes(self, message):
        # Any published edit must already be readable through the business DB.
        if message[:2] == b"\x00\x02":
            async with self.collaboration.factory() as session:
                chapter = await session.get(Chapter, self.collaboration.chapter.id)
                assert chapter.content == text_of(self.collaboration.room.document)
        self.messages.append(message)

    async def close(self, **kwargs):
        pass


def attach(collaboration):
    socket = Socket(collaboration)
    client = service.Client(socket)
    collaboration.room.clients.add(client)
    return client, socket


async def test_human_and_agent_sync_rollback_and_recover_without_subprocess(
    collaboration,
):
    c = collaboration
    first, first_socket = attach(c)
    second, second_socket = attach(c)
    first_document = clone_document(c.room.document)
    second_document = clone_document(c.room.document)
    tail = first_document.get("default", type=XmlFragment).children[1].children[0]
    assert isinstance(tail, XmlText)
    tail.insert(len(tail), " and bells")
    await c.hub.handle_message(
        c.name,
        first,
        create_update_message(first_document.get_update(c.room.document.get_state())),
    )
    result = json.loads(
        await c.tool._execute(
            volume_ref={"type": "order", "value": 1},
            chapter_ref={"type": "order", "value": 1},
            old_content="Sunny morning",
            new_content="Rain everywhere",
        )
    )
    assert result["success"]
    for document, socket in [
        (first_document, first_socket),
        (second_document, second_socket),
    ]:
        for message in socket.messages:
            if message[:2] == b"\x00\x02":
                handle_sync_message(message[1:], document)
        assert text_of(document) == "Rain everywhere\nThe end and bells"
    async with c.factory() as session:
        commits = await commit_repo.list_by_revision(session, c.revision.id)
        assert commits[0].snapshot_content == "Sunny morning\nThe end and bells"
        assert commits[0].new_content == "Rain everywhere\nThe end and bells"
    # A later human tail edit must survive reversing the Agent's head edit.
    human = clone_document(c.room.document)
    replace_exact(human, "The end and bells", "The end and bells ring")
    await c.hub.handle_message(
        c.name,
        first,
        create_update_message(human.get_update(c.room.document.get_state())),
    )
    async with c.factory() as session:
        async with service.chapter_lock(c.chapter.id):
            result = await service.prepare_rollback(
                session,
                {
                    c.chapter.id: SimpleNamespace(
                        exists=True, content="Sunny morning\nThe end and bells"
                    )
                },
                [c.revision],
            )
            assert (
                result[c.chapter.id]["content"]
                == "Sunny morning\nThe end and bells ring"
            )
            assert text_of(c.room.document).startswith("Rain everywhere")
            await session.commit()
            await service.publish_committed_updates(session)
    assert text_of(c.room.document) == "Sunny morning\nThe end and bells ring"
    await c.hub.stop()
    recovered = service.CollaborationHub()
    async with c.factory() as session:
        room = recovered.get_room(c.name, await service.load_document(session, c.name))
    assert text_of(room.document) == "Sunny morning\nThe end and bells ring"


async def test_failed_save_is_not_published_and_can_be_retried(
    collaboration, monkeypatch
):
    c = collaboration
    client, socket = attach(c)
    human = clone_document(c.room.document)
    replace_exact(human, "Sunny morning", "New morning")
    update = create_update_message(human.get_update(c.room.document.get_state()))
    original = service.persist_document
    monkeypatch.setattr(
        service, "persist_document", AsyncMock(side_effect=RuntimeError("write failed"))
    )
    with pytest.raises(RuntimeError, match="write failed"):
        await c.hub.handle_message(c.name, client, update)
    assert text_of(c.room.document) == "Sunny morning\nThe end"
    assert not socket.messages
    async with c.factory() as session:
        assert (
            await session.get(Chapter, c.chapter.id)
        ).content == "Sunny morning\nThe end"
    monkeypatch.setattr(service, "persist_document", original)
    await c.hub.handle_message(c.name, client, update)
    assert text_of(c.room.document) == "New morning\nThe end"


async def test_disabled_collaboration_refuses_pending_updates(collaboration):
    c = collaboration
    client, _ = attach(c)
    human = clone_document(c.room.document)
    replace_exact(human, "Sunny morning", "New morning")
    update = create_update_message(human.get_update(c.room.document.get_state()))
    await c.hub.pause()
    with pytest.raises(service.ConflictError):
        await c.hub.handle_message(c.name, client, update)
    async with c.factory() as session:
        assert (
            await session.get(Chapter, c.chapter.id)
        ).content == "Sunny morning\nThe end"


async def test_enabling_collaboration_needs_no_node_process_or_new_listener(
    tmp_path, monkeypatch
):
    import shutil
    import socket
    import subprocess
    from unittest.mock import Mock
    from app import settings as settings_module

    monkeypatch.setattr(settings_module, "BACKEND_DATA_DIR", tmp_path)
    monkeypatch.setattr(shutil, "which", Mock(return_value=None))
    forbidden = Mock(side_effect=AssertionError("No process or listener permitted"))
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(socket.socket, "bind", forbidden)
    hub = service.CollaborationHub()
    try:
        await hub.resume()
        assert hub.started and not hub.paused
        await hub.pause()
        assert hub.paused
        forbidden.assert_not_called()
    finally:
        await hub.stop()
