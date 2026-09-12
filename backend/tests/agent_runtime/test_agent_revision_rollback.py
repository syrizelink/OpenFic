import json

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.agent_runtime.persistence.model import AgentAttachment
from app.agent_runtime.persistence import repo as message_repo
from app.storage.models.chapter import Chapter
from app.storage.models.character import Character
from app.storage.models.note import Note, NoteCategory
from app.storage.models.project import Project
from app.storage.models.revision_chapter_snapshot import RevisionChapterSnapshot
from app.storage.models.task import Task
from app.storage.models.volume import Volume
from app.storage.models.world_info import WorldInfo
from app.storage.models.world_info_entry import WorldInfoEntry
from tests.model_registry import register_sqlmodel_models


@pytest_asyncio.fixture
async def revision_db(monkeypatch):
    register_sqlmodel_models()

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with factory() as session:
        session.add(Project(id="proj-1", title="Proyek Uji"))
        session.add(
            Volume(
                id="vol-1",
                project_id="proj-1",
                title="Volume 1",
                order=1,
                chapter_count=2,
            )
        )
        session.add(
            Chapter(
                id="chap-1",
                project_id="proj-1",
                volume_id="vol-1",
                title="Bab 1",
                content="Isi lama satu",
                word_count=4,
                order=1,
            )
        )
        session.add(
            Chapter(
                id="chap-2",
                project_id="proj-1",
                volume_id="vol-1",
                title="Bab 2",
                content="Isi lama dua",
                word_count=4,
                order=2,
            )
        )
        session.add(
            Task(
                id="task-1",
                project_id="proj-1",
                title="Agent Session",
                mode="agent",
                agent_session_id="sess-1",
            )
        )
        session.add(
            WorldInfo(
                id="world-1",
                project_id="proj-1",
                name="Buku Dunia Uji",
            )
        )
        session.add(
            WorldInfoEntry(
                id="entry-1",
                world_info_id="world-1",
                uid=1,
                name="Entri Lama",
                order=1,
                content="Setelan awal",
                token_count=4,
                is_enabled=True,
            )
        )
        session.add(
            Character(
                id="char-1",
                project_id="proj-1",
                name="Tokoh Lama",
                description="Deskripsi tokoh awal",
                is_favorited=False,
            )
        )
        session.add(
            NoteCategory(
                id="cat-1",
                project_id="proj-1",
                title="Setelan",
            )
        )
        session.add(
            Note(
                id="note-1",
                project_id="proj-1",
                category_id="cat-1",
                title="Catatan Lama",
                content="Isi awal",
            )
        )
        await session.commit()

    async def create_test_session():
        return factory()

    monkeypatch.setattr(
        "app.agent_runtime.tools.impls.chapter.write_chapter.create_session",
        create_test_session,
    )
    monkeypatch.setattr(
        "app.agent_runtime.tools.impls.chapter.delete_chapter.create_session",
        create_test_session,
    )
    monkeypatch.setattr(
        "app.agent_runtime.tools.impls.note.write_note.create_session",
        create_test_session,
    )
    monkeypatch.setattr(
        "app.agent_runtime.tools.impls.note.edit_note.create_session",
        create_test_session,
    )
    monkeypatch.setattr(
        "app.agent_runtime.tools.impls.note.delete_note.create_session",
        create_test_session,
    )
    monkeypatch.setattr(
        "app.agent_runtime.tools.impls.note.move_note.create_session",
        create_test_session,
    )
    monkeypatch.setattr(
        "app.agent_runtime.tools.impls.note.create_note_category.create_session",
        create_test_session,
    )
    monkeypatch.setattr(
        "app.agent_runtime.tools.impls.context.world_entry.create_session",
        create_test_session,
    )
    monkeypatch.setattr(
        "app.agent_runtime.tools.impls.context.character.create_session",
        create_test_session,
    )

    yield factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_write_chapter_records_current_revision_and_structured_result(revision_db):
    from app.agent_runtime.revisions import begin_user_revision
    from app.agent_runtime.tools.impls.chapter.write_chapter import WriteChapterTool
    from app.storage.repos import commit_repo, revision_chapter_snapshot_repo

    async with revision_db() as session:
        user = await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="user",
            status="sent",
            content="sisipkan satu bab",
        )
        revision = await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=user.id,
            user_message_seq=user.seq,
            message="Pesan pengguna: sisipkan satu bab",
            pre_run_checkpoint_id="cp-before",
            graph_thread_id="sess-1",
        )
        await session.commit()

    tool = WriteChapterTool(
        _state={
            "session_id": "sess-1",
            "task_id": "task-1",
            "project_id": "proj-1",
            "current_revision_id": revision.id,
        }
    )
    result = await tool.ainvoke(
        {
            "volume_ref": {"type": "order", "value": 1},
            "title": "Bab Sisipan",
            "content": "Isi konten baru",
            "chapter_ref": {"type": "order", "value": 2},
        }
    )

    payload = json.loads(result)
    chapter_diff = payload["metadata"]["chapter_diff"]
    assert payload["success"] is True
    assert payload["word_count"] == 3
    assert chapter_diff["chapter_title"] == "Bab Sisipan"
    assert chapter_diff["order"] == 2

    async with revision_db() as session:
        chapters = await session.execute(
            Chapter.__table__.select().where(Chapter.project_id == "proj-1")
        )
        rows = chapters.mappings().all()
        inserted_row = next(row for row in rows if row["title"] == "Bab Sisipan")
        commits = await commit_repo.list_by_revision(session, revision.id)
        snapshots = await revision_chapter_snapshot_repo.list_by_revision(
            session, revision.id
        )
    inserted_id = chapter_diff["chapter_id"]
    assert inserted_row["order"] == 2
    assert {(item.chapter_id, item.operation) for item in commits} == {
        (inserted_id, "create"),
        ("chap-2", "update"),
    }
    assert {(item.chapter_id, item.exists) for item in snapshots} == {
        (inserted_id, False),
        ("chap-2", True),
    }


@pytest.mark.asyncio
async def test_rollback_second_subagent_revision_restores_chapter_to_first_revision_content(
    revision_db,
    monkeypatch,
):
    from app.agent_runtime.revisions import begin_user_revision, rollback_revision_for_session
    from app.agent_runtime.tools.impls.chapter.edit_chapter import EditChapterTool
    from app.agent_runtime.tools.impls.chapter.write_chapter import WriteChapterTool
    from app.storage.repos import chapter_repo

    async def create_test_session():
        return revision_db()

    monkeypatch.setattr(
        "app.agent_runtime.tools.impls.chapter.edit_chapter.create_session",
        create_test_session,
    )

    async with revision_db() as session:
        first_user = await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="user",
            status="sent",
            content="delegasikan subagent membuat bab",
        )
        first_revision = await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=first_user.id,
            user_message_seq=first_user.seq,
            message="Pesan pengguna: delegasikan subagent membuat bab",
            pre_run_checkpoint_id="cp-before-first",
            graph_thread_id="sess-1",
        )
        await session.commit()

    write_tool = WriteChapterTool(
        _state={
            "session_id": "sess-1:child:writer",
            "task_id": "task-1",
            "project_id": "proj-1",
            "current_revision_id": first_revision.id,
        }
    )
    write_result = json.loads(
        await write_tool.ainvoke(
            {
                "volume_ref": {"type": "order", "value": 1},
                "title": "Subagent Bab",
                "content": "Halo",
            }
        )
    )
    chapter_id = write_result["metadata"]["chapter_diff"]["chapter_id"]

    async with revision_db() as session:
        second_user = await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="user",
            status="sent",
            content="minta subagent menyunting bab",
        )
        second_revision = await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=second_user.id,
            user_message_seq=second_user.seq,
            message="Pesan pengguna: minta subagent menyunting bab",
            pre_run_checkpoint_id="cp-before-second",
            graph_thread_id="sess-1",
        )
        await session.commit()

    edit_tool = EditChapterTool(
        _state={
            "session_id": "sess-1:child:writer",
            "task_id": "task-1",
            "project_id": "proj-1",
            "current_revision_id": second_revision.id,
        }
    )
    edit_result = json.loads(
        await edit_tool.ainvoke(
            {
                "volume_ref": {"type": "order", "value": 1},
                "chapter_ref": {"type": "title", "value": "Subagent Bab"},
                "old_content": "Halo",
                "new_content": "Hello",
            }
        )
    )
    assert edit_result.get("success") is True, edit_result

    async with revision_db() as session:
        edited = await chapter_repo.get_by_id(session, chapter_id)
        assert edited is not None
        assert edited.content == "Hello"
        await rollback_revision_for_session(
            session,
            agent_session_id="sess-1",
            revision_id=second_revision.id,
        )
        await session.commit()

    async with revision_db() as session:
        restored = await chapter_repo.get_by_id(session, chapter_id)

    assert restored is not None
    assert restored.content == "Halo"


@pytest.mark.asyncio
async def test_rollback_revision_restores_chapters_and_messages(revision_db):
    from app.agent_runtime.revisions import (
        begin_user_revision,
        rollback_revision_for_session,
    )
    from app.agent_runtime.tools.impls.chapter.write_chapter import WriteChapterTool
    from app.storage.repos import revision_repo

    async with revision_db() as session:
        user = await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="user",
            status="sent",
            content="sisipkan satu bab",
        )
        revision = await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=user.id,
            user_message_seq=user.seq,
            message="Pesan pengguna: sisipkan satu bab",
            pre_run_checkpoint_id="cp-before",
            graph_thread_id="sess-1",
        )
        await session.commit()

    tool = WriteChapterTool(
        _state={
            "session_id": "sess-1",
            "task_id": "task-1",
            "project_id": "proj-1",
            "current_revision_id": revision.id,
        }
    )
    result = json.loads(
        await tool.ainvoke(
            {
                "volume_ref": {"type": "order", "value": 1},
                "title": "Bab Sisipan",
                "content": "Isi konten baru",
                "chapter_ref": {"type": "order", "value": 2},
            }
        )
    )
    assert result["success"] is True
    inserted_id = result["metadata"]["chapter_diff"]["chapter_id"]

    async with revision_db() as session:
        await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="assistant",
            status="complete",
            content="Sudah disisipkan",
        )
        await session.commit()

    async with revision_db() as session:
        rollback_result = await rollback_revision_for_session(
            session,
            agent_session_id="sess-1",
            revision_id=revision.id,
        )
        await session.commit()

    assert rollback_result.restored_message_content == "sisipkan satu bab"
    assert set(rollback_result.affected_chapters) == {inserted_id, "chap-2"}

    async with revision_db() as session:
        chapters = await session.execute(
            Chapter.__table__.select().where(Chapter.project_id == "proj-1")
        )
        rows = sorted(chapters.mappings().all(), key=lambda row: row["order"])
        messages = await message_repo.list_by_session(session, "sess-1")
        rolled_back = await revision_repo.get_by_id(session, revision.id)
        task = await session.get(Task, "task-1")

    assert [(row["id"], row["order"]) for row in rows] == [("chap-1", 1), ("chap-2", 2)]
    assert inserted_id not in {row["id"] for row in rows}
    assert messages == []
    assert rolled_back is not None
    assert rolled_back.status == "rolled_back"
    assert task is not None


@pytest.mark.asyncio
async def test_rollback_preserves_target_message_attachments_for_resending(revision_db):
    from app.agent_runtime.revisions import (
        begin_user_revision,
        rollback_revision_for_session,
    )

    attachment_metadata = {
        "id": "attachment-1",
        "storage_name": "sess-1/attachment-1.png",
        "file_name": "reference.png",
        "mime_type": "image/png",
        "size_bytes": 12,
        "width": 2,
        "height": 3,
        "url": "/agent-attachments/sess-1/attachment-1.png",
    }
    async with revision_db() as session:
        session.add(
            AgentAttachment(
                id="attachment-1",
                session_id="sess-1",
                task_id="task-1",
                project_id="proj-1",
                storage_name="sess-1/attachment-1.png",
                file_name="reference.png",
                mime_type="image/png",
                size_bytes=12,
                width=2,
                height=3,
            )
        )
        user_message = await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="user",
            status="sent",
            content="silakan lihat gambar",
            metadata={"attachments": [attachment_metadata]},
        )
        revision = await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=user_message.id,
            user_message_seq=user_message.seq,
            message="Pesan pengguna: silakan lihat gambar",
            pre_run_checkpoint_id="cp-before",
            graph_thread_id="sess-1",
        )
        await session.commit()

    async with revision_db() as session:
        result = await rollback_revision_for_session(
            session,
            agent_session_id="sess-1",
            revision_id=revision.id,
        )
        await session.commit()

    assert result.restored_message_content == "silakan lihat gambar"
    assert result.restored_attachments == [attachment_metadata]

    async with revision_db() as session:
        assert await session.get(AgentAttachment, "attachment-1") is not None


@pytest.mark.asyncio
async def test_rollback_rejects_oversized_chapter_snapshot_before_mutating(revision_db):
    from app.agent_runtime.revisions import (
        begin_user_revision,
        rollback_revision_for_session,
    )
    from app.storage.repos import chapter_repo, revision_chapter_snapshot_repo, revision_repo

    async with revision_db() as session:
        user = await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="user",
            status="sent",
            content="pulihkan bab melebihi batas",
        )
        target_revision = await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=user.id,
            user_message_seq=user.seq,
            message="Pesan pengguna: pulihkan bab melebihi batas",
            pre_run_checkpoint_id="cp-before",
            graph_thread_id="sess-1",
        )
        await revision_chapter_snapshot_repo.create(
            session,
            RevisionChapterSnapshot(
                revision_id=target_revision.id,
                chapter_id="chap-1",
                project_id="proj-1",
                exists=True,
                title="Bab 1",
                content="\n".join("Isi melebihi batas" for _ in range(2001)),
                word_count=0,
                chapter_order=1,
            ),
        )
        chapter = await chapter_repo.get_by_id(session, "chap-1")
        assert chapter is not None
        chapter.content = "Isi sebelum rollback"
        await chapter_repo.update_chapter(session, chapter)
        await session.commit()

    async with revision_db() as session:
        with pytest.raises(ValueError, match="Konten melebihi batas"):
            await rollback_revision_for_session(
                session,
                agent_session_id="sess-1",
                revision_id=target_revision.id,
            )
        await session.commit()

    async with revision_db() as session:
        chapter = await chapter_repo.get_by_id(session, "chap-1")
        target_after = await revision_repo.get_by_id(session, target_revision.id)
        revisions = await revision_repo.list_by_agent_session_from_seq(
            session,
            "sess-1",
            target_revision.user_message_seq,
        )

    assert chapter is not None
    assert chapter.content == "Isi sebelum rollback"
    assert target_after is not None
    assert target_after.status != "rolled_back"
    assert all(revision.revision_type != "rollback" for revision in revisions)


@pytest.mark.asyncio
async def test_rollback_revision_deletes_compactions_intersecting_deleted_messages(
    revision_db,
):
    from app.agent_runtime.persistence import compaction_repo
    from app.agent_runtime.revisions import (
        begin_user_revision,
        rollback_revision_for_session,
    )

    async with revision_db() as session:
        await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="user",
            status="sent",
            content="Putaran pertama",
        )
        await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="assistant",
            status="complete",
            content="Balasan putaran pertama",
        )
        await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="assistant",
            status="complete",
            content="Balasan awal putaran kedua",
        )
        target_user = await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="user",
            status="sent",
            content="target rollback",
        )
        target_revision = await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=target_user.id,
            user_message_seq=target_user.seq,
            message="Pesan pengguna: target rollback",
            pre_run_checkpoint_id="cp-before-target",
            graph_thread_id="sess-1",
        )
        await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="assistant",
            status="complete",
            content="Balasan yang akan dihapus",
        )
        await compaction_repo.insert_compaction(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            start_seq=0,
            end_seq=1,
            summary="Kompaksi yang dipertahankan",
            trigger="manual",
        )
        await compaction_repo.insert_compaction(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            start_seq=2,
            end_seq=4,
            summary="Kompaksi yang beririsan dengan rentang hapus rollback",
            trigger="manual",
        )
        await session.commit()

    async with revision_db() as session:
        await rollback_revision_for_session(
            session,
            agent_session_id="sess-1",
            revision_id=target_revision.id,
        )
        await session.commit()

    async with revision_db() as session:
        rows = await compaction_repo.list_by_session(session, "sess-1")

    assert [(row.start_seq, row.end_seq, row.summary) for row in rows] == [
        (0, 1, "Kompaksi yang dipertahankan"),
    ]


@pytest.mark.asyncio
async def test_write_note_records_revision_snapshot(revision_db):
    from app.agent_runtime.revisions import begin_user_revision
    from app.agent_runtime.tools.impls.note.write_note import WriteNoteTool
    from app.storage.repos import revision_note_snapshot_repo

    async with revision_db() as session:
        user = await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="user",
            status="sent",
            content="buat satu catatan",
        )
        revision = await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=user.id,
            user_message_seq=user.seq,
            message="Pesan pengguna: buat satu catatan",
            pre_run_checkpoint_id="cp-before",
            graph_thread_id="sess-1",
        )
        await session.commit()

    tool = WriteNoteTool(
        _state={
            "session_id": "sess-1",
            "task_id": "task-1",
            "project_id": "proj-1",
            "current_revision_id": revision.id,
        }
    )
    result = json.loads(
        await tool.ainvoke(
            {"title": "Catatan Baru", "content": "Isi konten baru", "category_ref": {"id": "cat-1"}}
        )
    )
    assert result["success"] is True
    created_id = result["metadata"]["note_diff"]["note_id"]

    async with revision_db() as session:
        snapshots = await revision_note_snapshot_repo.list_by_revision(
            session, revision.id
        )

    assert {(item.note_id, item.exists) for item in snapshots} == {
        (created_id, False),
    }


@pytest.mark.asyncio
async def test_rollback_revision_restores_notes(revision_db):
    from app.agent_runtime.revisions import (
        begin_user_revision,
        rollback_revision_for_session,
    )
    from app.agent_runtime.tools.impls.note.delete_note import DeleteNoteTool
    from app.agent_runtime.tools.impls.note.edit_note import EditNoteTool
    from app.agent_runtime.tools.impls.note.write_note import WriteNoteTool
    from app.storage.repos import note_repo

    async with revision_db() as session:
        user = await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="user",
            status="sent",
            content="operasikan catatan",
        )
        revision = await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=user.id,
            user_message_seq=user.seq,
            message="Pesan pengguna: operasikan catatan",
            pre_run_checkpoint_id="cp-before",
            graph_thread_id="sess-1",
        )
        await session.commit()

    state = {
        "session_id": "sess-1",
        "task_id": "task-1",
        "project_id": "proj-1",
        "current_revision_id": revision.id,
    }

    write_tool = WriteNoteTool(_state=state)
    write_result = json.loads(
        await write_tool.ainvoke(
            {"title": "Catatan Sementara", "content": "Akan dihapus oleh rollback", "category_ref": {"id": "cat-1"}}
        )
    )
    assert write_result["success"] is True
    created_id = write_result["metadata"]["note_diff"]["note_id"]

    edit_tool = EditNoteTool(_state=state)
    edit_result = json.loads(
        await edit_tool.ainvoke(
            {
                "note_ref": {"id": "note-1"},
                "old_content": "Isi awal",
                "new_content": "Isi yang telah diubah",
            }
        )
    )
    assert edit_result["success"] is True

    delete_tool = DeleteNoteTool(_state=state)
    delete_result = json.loads(
        await delete_tool.ainvoke({"note_ref": {"id": "note-1"}})
    )
    assert delete_result["success"] is True

    async with revision_db() as session:
        rollback_result = await rollback_revision_for_session(
            session,
            agent_session_id="sess-1",
            revision_id=revision.id,
        )
        await session.commit()

    assert set(rollback_result.affected_notes) == {created_id, "note-1"}

    async with revision_db() as session:
        created_after = await note_repo.get_by_id(session, created_id)
        original_after = await note_repo.get_by_id(session, "note-1")
        all_notes = await note_repo.list_by_project(session, "proj-1")

    assert created_after is None
    assert original_after is not None
    assert original_after.title == "Catatan Lama"
    assert original_after.content == "Isi awal"
    assert {n.id for n in all_notes} == {"note-1"}


@pytest.mark.asyncio
async def test_rollback_revision_restores_moved_note(revision_db):
    from app.agent_runtime.revisions import (
        begin_user_revision,
        rollback_revision_for_session,
    )
    from app.agent_runtime.tools.impls.note.move_note import MoveNoteTool
    from app.storage.repos import note_repo

    async with revision_db() as session:
        session.add(
            NoteCategory(
                id="cat-2",
                project_id="proj-1",
                title="Tokoh",
            )
        )
        await session.commit()

    async with revision_db() as session:
        user = await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="user",
            status="sent",
            content="pindahkan catatan",
        )
        revision = await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=user.id,
            user_message_seq=user.seq,
            message="Pesan pengguna: pindahkan catatan",
            pre_run_checkpoint_id="cp-before",
            graph_thread_id="sess-1",
        )
        await session.commit()

    move_tool = MoveNoteTool(
        _state={
            "session_id": "sess-1",
            "task_id": "task-1",
            "project_id": "proj-1",
            "current_revision_id": revision.id,
        }
    )
    move_result = json.loads(
        await move_tool.ainvoke(
            {"note_ref": {"id": "note-1"}, "target_category_ref": {"id": "cat-2"}}
        )
    )
    assert move_result["success"] is True

    async with revision_db() as session:
        await rollback_revision_for_session(
            session,
            agent_session_id="sess-1",
            revision_id=revision.id,
        )
        await session.commit()

    async with revision_db() as session:
        note = await note_repo.get_by_id(session, "note-1")

    assert note is not None
    assert note.category_id == "cat-1"


@pytest.mark.asyncio
async def test_create_note_category_records_revision_snapshot(revision_db):
    from app.agent_runtime.revisions import begin_user_revision
    from app.agent_runtime.tools.impls.note.create_note_category import (
        CreateNoteCategoryTool,
    )
    from app.storage.repos import revision_note_snapshot_repo

    async with revision_db() as session:
        user = await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="user",
            status="sent",
            content="buat satu kategori",
        )
        revision = await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=user.id,
            user_message_seq=user.seq,
            message="Pesan pengguna: buat satu kategori",
            pre_run_checkpoint_id="cp-before",
            graph_thread_id="sess-1",
        )
        await session.commit()

    tool = CreateNoteCategoryTool(
        _state={
            "session_id": "sess-1",
            "task_id": "task-1",
            "project_id": "proj-1",
            "current_revision_id": revision.id,
        }
    )
    result = json.loads(
        await tool.ainvoke({"title": "Kategori Baru", "parent_ref": {"id": "cat-1"}})
    )
    assert result["success"] is True
    created_id = result["metadata"]["category"]["id"]

    async with revision_db() as session:
        snapshots = (
            await revision_note_snapshot_repo.list_category_snapshots_by_revision(
                session, revision.id
            )
        )

    assert {(item.category_id, item.exists) for item in snapshots} == {
        (created_id, False),
    }


@pytest.mark.asyncio
async def test_rollback_revision_restores_note_categories(revision_db):
    from app.agent_runtime.revisions import (
        begin_user_revision,
        rollback_revision_for_session,
    )
    from app.agent_runtime.tools.impls.note.create_note_category import (
        CreateNoteCategoryTool,
    )
    from app.storage.repos import note_category_repo

    async with revision_db() as session:
        user = await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="user",
            status="sent",
            content="buat kategori",
        )
        revision = await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=user.id,
            user_message_seq=user.seq,
            message="Pesan pengguna: buat kategori",
            pre_run_checkpoint_id="cp-before",
            graph_thread_id="sess-1",
        )
        await session.commit()

    state = {
        "session_id": "sess-1",
        "task_id": "task-1",
        "project_id": "proj-1",
        "current_revision_id": revision.id,
    }

    create_tool = CreateNoteCategoryTool(_state=state)
    create_result = json.loads(
        await create_tool.ainvoke({"title": "Kategori Sementara", "parent_ref": {"id": "cat-1"}})
    )
    assert create_result["success"] is True
    created_id = create_result["metadata"]["category"]["id"]

    async with revision_db() as session:
        rollback_result = await rollback_revision_for_session(
            session,
            agent_session_id="sess-1",
            revision_id=revision.id,
        )
        await session.commit()

    assert set(rollback_result.affected_note_categories) == {created_id}

    async with revision_db() as session:
        created_after = await note_category_repo.get_by_id(session, created_id)
        all_cats = await note_category_repo.list_by_project(session, "proj-1")

    assert created_after is None
    assert {c.id for c in all_cats} == {"cat-1"}


@pytest.mark.asyncio
async def test_rollback_restores_nested_category_before_note(revision_db):
    from app.agent_runtime.revisions import (
        begin_user_revision,
        rollback_revision_for_session,
    )
    from app.agent_runtime.tools.impls.note.create_note_category import (
        CreateNoteCategoryTool,
    )
    from app.agent_runtime.tools.impls.note.write_note import WriteNoteTool
    from app.storage.repos import note_category_repo, note_repo

    async with revision_db() as session:
        user = await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="user",
            status="sent",
            content="buat kategori bersarang dan catatan",
        )
        revision = await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=user.id,
            user_message_seq=user.seq,
            message="Pesan pengguna: buat kategori bersarang dan catatan",
            pre_run_checkpoint_id="cp-before",
            graph_thread_id="sess-1",
        )
        await session.commit()

    state = {
        "session_id": "sess-1",
        "task_id": "task-1",
        "project_id": "proj-1",
        "current_revision_id": revision.id,
    }

    cat_tool = CreateNoteCategoryTool(_state=state)
    cat_result = json.loads(
        await cat_tool.ainvoke({"title": "Kategori Induk Baru"})
    )
    assert cat_result["success"] is True
    new_cat_id = cat_result["metadata"]["category"]["id"]

    sub_cat_tool = CreateNoteCategoryTool(_state=state)
    sub_cat_result = json.loads(
        await sub_cat_tool.ainvoke(
            {"title": "Subkategori", "parent_ref": {"id": new_cat_id}}
        )
    )
    assert sub_cat_result["success"] is True
    sub_cat_id = sub_cat_result["metadata"]["category"]["id"]

    write_tool = WriteNoteTool(_state=state)
    write_result = json.loads(
        await write_tool.ainvoke(
            {"title": "Catatan Bersarang", "content": "Isi", "category_ref": {"id": sub_cat_id}}
        )
    )
    assert write_result["success"] is True
    note_id = write_result["metadata"]["note_diff"]["note_id"]

    async with revision_db() as session:
        rollback_result = await rollback_revision_for_session(
            session,
            agent_session_id="sess-1",
            revision_id=revision.id,
        )
        await session.commit()

    assert set(rollback_result.affected_note_categories) == {
        new_cat_id,
        sub_cat_id,
    }
    assert set(rollback_result.affected_notes) == {note_id}

    async with revision_db() as session:
        new_cat_after = await note_category_repo.get_by_id(session, new_cat_id)
        sub_cat_after = await note_category_repo.get_by_id(session, sub_cat_id)
        note_after = await note_repo.get_by_id(session, note_id)
        all_cats = await note_category_repo.list_by_project(session, "proj-1")

    assert new_cat_after is None
    assert sub_cat_after is None
    assert note_after is None
    assert {c.id for c in all_cats} == {"cat-1"}


@pytest.mark.asyncio
async def test_rollback_revision_restores_created_world_entries(revision_db):
    from app.agent_runtime.revisions import (
        begin_user_revision,
        rollback_revision_for_session,
    )
    from app.agent_runtime.tools.impls.context.world_entry import CreateWorldEntryTool
    from app.storage.repos import world_info_entry_repo

    async with revision_db() as session:
        user = await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="user",
            status="sent",
            content="buat entri buku dunia",
        )
        revision = await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=user.id,
            user_message_seq=user.seq,
            message="Pesan pengguna: buat entri buku dunia",
            pre_run_checkpoint_id="cp-before",
            graph_thread_id="sess-1",
        )
        await session.commit()

    tool = CreateWorldEntryTool(
        _state={
            "session_id": "sess-1",
            "task_id": "task-1",
            "project_id": "proj-1",
            "current_revision_id": revision.id,
        }
    )
    result = json.loads(
        await tool.ainvoke({"title": "Entri Sementara", "content": "Setelan sementara"})
    )
    assert result["success"] is True
    entry_id = result["metadata"]["world_entry_diff"]["entry_id"]

    async with revision_db() as session:
        rollback_result = await rollback_revision_for_session(
            session,
            agent_session_id="sess-1",
            revision_id=revision.id,
        )
        await session.commit()

    assert set(rollback_result.affected_world_entries) == {entry_id}

    async with revision_db() as session:
        entry_after = await world_info_entry_repo.get_by_id(session, entry_id)

    assert entry_after is None


@pytest.mark.asyncio
async def test_rollback_revision_restores_edited_world_entries(revision_db):
    from app.agent_runtime.revisions import (
        begin_user_revision,
        rollback_revision_for_session,
    )
    from app.agent_runtime.tools.impls.context.world_entry import EditWorldEntryTool
    from app.storage.repos import world_info_entry_repo

    async with revision_db() as session:
        user = await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="user",
            status="sent",
            content="sunting entri buku dunia",
        )
        revision = await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=user.id,
            user_message_seq=user.seq,
            message="Pesan pengguna: sunting entri buku dunia",
            pre_run_checkpoint_id="cp-before",
            graph_thread_id="sess-1",
        )
        await session.commit()

    tool = EditWorldEntryTool(
        _state={
            "session_id": "sess-1",
            "task_id": "task-1",
            "project_id": "proj-1",
            "current_revision_id": revision.id,
        }
    )
    result = json.loads(
        await tool.ainvoke(
            {
                "title": "Entri Lama",
                "new_title": "Entri Ganti Nama",
                "old_content": "awal",
                "new_content": "diperbarui",
            }
        )
    )
    assert result["success"] is True

    async with revision_db() as session:
        rollback_result = await rollback_revision_for_session(
            session,
            agent_session_id="sess-1",
            revision_id=revision.id,
        )
        await session.commit()

    assert set(rollback_result.affected_world_entries) == {"entry-1"}

    async with revision_db() as session:
        entry_after = await world_info_entry_repo.get_by_id(session, "entry-1")

    assert entry_after is not None
    assert entry_after.name == "Entri Lama"
    assert entry_after.content == "Setelan awal"


@pytest.mark.asyncio
async def test_rollback_revision_restores_deleted_world_entries(revision_db):
    from app.agent_runtime.revisions import (
        begin_user_revision,
        rollback_revision_for_session,
    )
    from app.agent_runtime.tools.impls.context.world_entry import DeleteWorldEntryTool
    from app.storage.repos import world_info_entry_repo

    async with revision_db() as session:
        user = await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="user",
            status="sent",
            content="hapus entri buku dunia",
        )
        revision = await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=user.id,
            user_message_seq=user.seq,
            message="Pesan pengguna: hapus entri buku dunia",
            pre_run_checkpoint_id="cp-before",
            graph_thread_id="sess-1",
        )
        await session.commit()

    tool = DeleteWorldEntryTool(
        _state={
            "session_id": "sess-1",
            "task_id": "task-1",
            "project_id": "proj-1",
            "current_revision_id": revision.id,
        }
    )
    result = json.loads(await tool.ainvoke({"title": "Entri Lama"}))
    assert result["success"] is True

    async with revision_db() as session:
        rollback_result = await rollback_revision_for_session(
            session,
            agent_session_id="sess-1",
            revision_id=revision.id,
        )
        await session.commit()

    assert set(rollback_result.affected_world_entries) == {"entry-1"}

    async with revision_db() as session:
        entry_after = await world_info_entry_repo.get_by_id(session, "entry-1")

    assert entry_after is not None
    assert entry_after.name == "Entri Lama"
    assert entry_after.content == "Setelan awal"


@pytest.mark.asyncio
async def test_rollback_revision_restores_created_characters(revision_db):
    from app.agent_runtime.revisions import (
        begin_user_revision,
        rollback_revision_for_session,
    )
    from app.agent_runtime.tools.impls.context.character import CreateCharacterTool
    from app.storage.repos import character_repo

    async with revision_db() as session:
        user = await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="user",
            status="sent",
            content="buat tokoh",
        )
        revision = await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=user.id,
            user_message_seq=user.seq,
            message="Pesan pengguna: buat tokoh",
            pre_run_checkpoint_id="cp-before",
            graph_thread_id="sess-1",
        )
        await session.commit()

    tool = CreateCharacterTool(
        _state={
            "session_id": "sess-1",
            "task_id": "task-1",
            "project_id": "proj-1",
            "current_revision_id": revision.id,
        }
    )
    result = json.loads(await tool.ainvoke({"name": "Tokoh Sementara", "description": "Deskripsi sementara"}))
    assert result["success"] is True
    character_id = result["metadata"]["character_diff"]["character_id"]

    async with revision_db() as session:
        rollback_result = await rollback_revision_for_session(
            session,
            agent_session_id="sess-1",
            revision_id=revision.id,
        )
        await session.commit()

    assert set(rollback_result.affected_characters) == {character_id}

    async with revision_db() as session:
        character_after = await character_repo.get_by_id(session, character_id)

    assert character_after is None


@pytest.mark.asyncio
async def test_rollback_revision_restores_edited_characters(revision_db):
    from app.agent_runtime.revisions import (
        begin_user_revision,
        rollback_revision_for_session,
    )
    from app.agent_runtime.tools.impls.context.character import EditCharacterTool
    from app.storage.repos import character_repo

    async with revision_db() as session:
        user = await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="user",
            status="sent",
            content="sunting tokoh",
        )
        revision = await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=user.id,
            user_message_seq=user.seq,
            message="Pesan pengguna: sunting tokoh",
            pre_run_checkpoint_id="cp-before",
            graph_thread_id="sess-1",
        )
        await session.commit()

    tool = EditCharacterTool(
        _state={
            "session_id": "sess-1",
            "task_id": "task-1",
            "project_id": "proj-1",
            "current_revision_id": revision.id,
        }
    )
    result = json.loads(
        await tool.ainvoke(
            {
                "name": "Tokoh Lama",
                "new_name": "Tokoh Ganti Nama",
                "old_description": "awal",
                "new_description": "diperbarui",
            }
        )
    )
    assert result["success"] is True

    async with revision_db() as session:
        rollback_result = await rollback_revision_for_session(
            session,
            agent_session_id="sess-1",
            revision_id=revision.id,
        )
        await session.commit()

    assert set(rollback_result.affected_characters) == {"char-1"}

    async with revision_db() as session:
        character_after = await character_repo.get_by_id(session, "char-1")

    assert character_after is not None
    assert character_after.name == "Tokoh Lama"
    assert character_after.description == "Deskripsi tokoh awal"
    assert character_after.is_favorited is False


@pytest.mark.asyncio
async def test_rollback_revision_restores_deleted_characters(revision_db):
    from app.agent_runtime.revisions import (
        begin_user_revision,
        rollback_revision_for_session,
    )
    from app.agent_runtime.tools.impls.context.character import DeleteCharacterTool
    from app.storage.repos import character_repo

    async with revision_db() as session:
        user = await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="user",
            status="sent",
            content="hapus tokoh",
        )
        revision = await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=user.id,
            user_message_seq=user.seq,
            message="Pesan pengguna: hapus tokoh",
            pre_run_checkpoint_id="cp-before",
            graph_thread_id="sess-1",
        )
        await session.commit()

    tool = DeleteCharacterTool(
        _state={
            "session_id": "sess-1",
            "task_id": "task-1",
            "project_id": "proj-1",
            "current_revision_id": revision.id,
        }
    )
    result = json.loads(await tool.ainvoke({"name": "Tokoh Lama"}))
    assert result["success"] is True

    async with revision_db() as session:
        rollback_result = await rollback_revision_for_session(
            session,
            agent_session_id="sess-1",
            revision_id=revision.id,
        )
        await session.commit()

    assert set(rollback_result.affected_characters) == {"char-1"}

    async with revision_db() as session:
        character_after = await character_repo.get_by_id(session, "char-1")

    assert character_after is not None
    assert character_after.name == "Tokoh Lama"
    assert character_after.description == "Deskripsi tokoh awal"
