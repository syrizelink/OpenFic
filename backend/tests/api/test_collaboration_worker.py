"""Real Node worker + SQL transaction integration, without an LLM provider."""

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.collaboration import service
from app.storage.models.chapter import Chapter
from app.storage.models.project import Project
from app.storage.models.volume import Volume
from app.storage.models.task import Task
from app.storage.models.revision import Revision
from app.storage.repos import setting_repo, commit_repo


@pytest.mark.skipif(
    shutil.which("node") is None
    or not (
        Path(service.__file__).with_name("server.bundle.cjs").exists()
        or (
            Path(__file__).resolve().parents[3]
            / "collaboration/node_modules/@hocuspocus/server"
        ).exists()
    ),
    reason="Build the collaboration worker with pnpm before running this integration test",
)
async def test_agent_edits_commit_binary_and_revision_before_publishing_then_recover(
    tmp_path, monkeypatch
):
    from app.agent_runtime.tools.impls.chapter import edit_chapter as tool_module
    from app.storage import database
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
    worker = service.CollaborationWorker()
    monkeypatch.setattr(service, "worker", worker)
    try:
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
            await session.commit()
            state = {
                "project_id": project.id,
                "session_id": "session",
                "task_id": task.id,
                "current_revision_id": revision.id,
            }
        tool = tool_module.EditChapterTool(_state=state)
        result = json.loads(
            await tool._execute(
                volume_ref={"type": "order", "value": 1},
                chapter_ref={"type": "order", "value": 1},
                old_content="Sunny morning",
                new_content="Rain everywhere",
            )
        )
        assert result["success"]
        async with factory() as session:
            current = await session.get(Chapter, chapter.id)
            assert current.content == "Rain everywhere\nThe end"
            record = await service.document_record(session, chapter.id)
            assert record.state
            commits = await commit_repo.list_by_revision(session, revision.id)
            assert commits[0].snapshot_content == "Sunny morning\nThe end"
            assert commits[0].new_content == "Rain everywhere\nThe end"
            room = service.room_for(record)
            saved = await service.load_document(session, room)
        await worker.stop()
        recovered = await worker.call("snapshot", room=room, seed=saved)
        assert recovered["content"] == "Rain everywhere\nThe end"
        # Simulate an unrelated human tail edit in the live Y.Doc and persist it.
        prepared = await worker.call(
            "edit",
            room=room,
            old_content="The end",
            new_content="The end and bells",
            replace_all=False,
        )
        await worker.call("apply", room=room, state=prepared["state"])
        async with factory() as session:
            async with service.chapter_lock(chapter.id):
                await service.persist_document(
                    session, await worker.call("snapshot", room=room)
                )
                await session.commit()
        # Reverse only the Agent's head edit; leave the human tail in place.
        rollback = await worker.call(
            "restore",
            room=room,
            edits=[
                {
                    "old": "Rain everywhere",
                    "text": "Sunny morning",
                    "left": "",
                    "right": "",
                    "unique": True,
                }
            ],
        )
        assert rollback["content"] == "Sunny morning\nThe end and bells"
        # Preparing an edit never changes what other editors see before commit.
        assert (await worker.call("snapshot", room=room))[
            "content"
        ] == "Rain everywhere\nThe end and bells"
        async with factory() as session:
            async with service.chapter_lock(chapter.id):
                results = await service.prepare_rollback(
                    session,
                    {
                        chapter.id: SimpleNamespace(
                            exists=True, content="Sunny morning\nThe end"
                        )
                    },
                    [revision],
                )
                assert (
                    results[chapter.id]["content"] == "Sunny morning\nThe end and bells"
                )
                await session.commit()
                await service.publish_committed_updates(session)
        assert (await worker.call("snapshot", room=room))[
            "content"
        ] == "Sunny morning\nThe end and bells"

    finally:
        await worker.stop()
        await engine.dispose()
