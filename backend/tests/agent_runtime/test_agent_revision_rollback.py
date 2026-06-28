import json

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.agent_runtime.persistence import repo as message_repo
from app.storage.models.chapter import Chapter
from app.storage.models.note import Note, NoteCategory
from app.storage.models.project import Project
from app.storage.models.task import Task
from app.storage.models.volume import Volume
from tests.model_registry import register_sqlmodel_models


@pytest_asyncio.fixture
async def revision_db(monkeypatch):
    register_sqlmodel_models()

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with factory() as session:
        session.add(Project(id="proj-1", title="测试项目"))
        session.add(
            Volume(
                id="vol-1",
                project_id="proj-1",
                title="第一卷",
                order=1,
                chapter_count=2,
            )
        )
        session.add(
            Chapter(
                id="chap-1",
                project_id="proj-1",
                volume_id="vol-1",
                title="第一章",
                content="旧内容一",
                word_count=4,
                order=1,
            )
        )
        session.add(
            Chapter(
                id="chap-2",
                project_id="proj-1",
                volume_id="vol-1",
                title="第二章",
                content="旧内容二",
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
            NoteCategory(
                id="cat-1",
                project_id="proj-1",
                title="设定",
            )
        )
        session.add(
            Note(
                id="note-1",
                project_id="proj-1",
                category_id="cat-1",
                title="已有笔记",
                content="原始内容",
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
            content="插入一个章节",
        )
        revision = await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=user.id,
            user_message_seq=user.seq,
            message="用户消息: 插入一个章节",
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
            "title": "插入章",
            "content": "新内容",
            "chapter_ref": {"type": "order", "value": 2},
        }
    )

    payload = json.loads(result)
    assert payload["success"] is True
    assert payload["tool_name"] == "write_chapter"
    assert payload["revision_id"] == revision.id
    assert payload["chapter"]["title"] == "插入章"
    assert payload["chapter"]["order"] == 2
    assert set(payload["affected_chapters"]) == {payload["chapter"]["id"], "chap-2"}

    async with revision_db() as session:
        chapters = await session.execute(
            Chapter.__table__.select().where(Chapter.project_id == "proj-1")
        )
        rows = chapters.mappings().all()
        inserted_row = next(row for row in rows if row["title"] == "插入章")
        commits = await commit_repo.list_by_revision(session, revision.id)
        snapshots = await revision_chapter_snapshot_repo.list_by_revision(
            session, revision.id
        )
    inserted_id = payload["chapter"]["id"]
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
            content="插入一个章节",
        )
        revision = await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=user.id,
            user_message_seq=user.seq,
            message="用户消息: 插入一个章节",
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
                "title": "插入章",
                "content": "新内容",
                "chapter_ref": {"type": "order", "value": 2},
            }
        )
    )
    assert result["success"] is True
    assert result["tool_name"] == "write_chapter"
    inserted_id = result["chapter"]["id"]

    async with revision_db() as session:
        await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="assistant",
            status="complete",
            content="已插入",
        )
        await session.commit()

    async with revision_db() as session:
        rollback_result = await rollback_revision_for_session(
            session,
            agent_session_id="sess-1",
            revision_id=revision.id,
        )
        await session.commit()

    assert rollback_result.restored_message_content == "插入一个章节"
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
            content="第一轮",
        )
        await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="assistant",
            status="complete",
            content="第一轮回复",
        )
        await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="assistant",
            status="complete",
            content="第二轮前置回复",
        )
        target_user = await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="user",
            status="sent",
            content="回滚目标",
        )
        target_revision = await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=target_user.id,
            user_message_seq=target_user.seq,
            message="用户消息: 回滚目标",
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
            content="将被删除的回复",
        )
        await compaction_repo.insert_compaction(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            start_seq=0,
            end_seq=1,
            summary="保留的压缩",
            trigger="manual",
        )
        await compaction_repo.insert_compaction(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            start_seq=2,
            end_seq=4,
            summary="与回滚删除范围相交的压缩",
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
        (0, 1, "保留的压缩"),
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
            content="创建一个笔记",
        )
        revision = await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=user.id,
            user_message_seq=user.seq,
            message="用户消息: 创建一个笔记",
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
            {"title": "新笔记", "content": "新内容", "category_ref": {"id": "cat-1"}}
        )
    )
    assert result["success"] is True
    assert result["tool_name"] == "write_note"
    assert result["revision_id"] == revision.id
    created_id = result["note"]["id"]
    assert set(result["affected_notes"]) == {created_id}

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
            content="操作笔记",
        )
        revision = await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=user.id,
            user_message_seq=user.seq,
            message="用户消息: 操作笔记",
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
            {"title": "临时笔记", "content": "将被回滚删除", "category_ref": {"id": "cat-1"}}
        )
    )
    assert write_result["success"] is True
    created_id = write_result["note"]["id"]

    edit_tool = EditNoteTool(_state=state)
    edit_result = json.loads(
        await edit_tool.ainvoke(
            {
                "note_ref": {"id": "note-1"},
                "old_content": "原始内容",
                "new_content": "被修改的内容",
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
    assert original_after.title == "已有笔记"
    assert original_after.content == "原始内容"
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
                title="角色",
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
            content="移动笔记",
        )
        revision = await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=user.id,
            user_message_seq=user.seq,
            message="用户消息: 移动笔记",
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
            content="创建一个分类",
        )
        revision = await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=user.id,
            user_message_seq=user.seq,
            message="用户消息: 创建一个分类",
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
        await tool.ainvoke({"title": "新分类", "parent_ref": {"id": "cat-1"}})
    )
    assert result["success"] is True
    assert result["tool_name"] == "create_note_category"
    assert result["revision_id"] == revision.id
    created_id = result["category"]["id"]
    assert set(result["affected_note_categories"]) == {created_id}

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
            content="创建分类",
        )
        revision = await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=user.id,
            user_message_seq=user.seq,
            message="用户消息: 创建分类",
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
        await create_tool.ainvoke({"title": "临时分类", "parent_ref": {"id": "cat-1"}})
    )
    assert create_result["success"] is True
    created_id = create_result["category"]["id"]

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
            content="创建嵌套分类和笔记",
        )
        revision = await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=user.id,
            user_message_seq=user.seq,
            message="用户消息: 创建嵌套分类和笔记",
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
        await cat_tool.ainvoke({"title": "新父分类"})
    )
    assert cat_result["success"] is True
    new_cat_id = cat_result["category"]["id"]

    sub_cat_tool = CreateNoteCategoryTool(_state=state)
    sub_cat_result = json.loads(
        await sub_cat_tool.ainvoke(
            {"title": "子分类", "parent_ref": {"id": new_cat_id}}
        )
    )
    assert sub_cat_result["success"] is True
    sub_cat_id = sub_cat_result["category"]["id"]

    write_tool = WriteNoteTool(_state=state)
    write_result = json.loads(
        await write_tool.ainvoke(
            {"title": "嵌套笔记", "content": "内容", "category_ref": {"id": sub_cat_id}}
        )
    )
    assert write_result["success"] is True
    note_id = write_result["note"]["id"]

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
