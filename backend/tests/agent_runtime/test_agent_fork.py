import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.agent_runtime.persistence import repo as message_repo
from app.storage.models.chapter import Chapter
from app.storage.models.project import Project
from app.storage.models.task import Task
from app.storage.models.volume import Volume
from tests.model_registry import register_sqlmodel_models


@pytest_asyncio.fixture
async def fork_db():
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
                chapter_count=1,
            )
        )
        session.add(
            Chapter(
                id="chap-1",
                project_id="proj-1",
                volume_id="vol-1",
                title="第一章",
                content="当前内容",
                word_count=4,
                order=1,
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
        await session.commit()

    yield factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_fork_clones_history_to_target_round_without_inherited_rollback(fork_db):
    from app.agent_runtime.fork import fork_agent_session_at_revision
    from app.agent_runtime.revisions import begin_user_revision

    async with fork_db() as session:
        first_user = await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="user",
            status="sent",
            content="第一轮",
        )
        first_revision = await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=first_user.id,
            user_message_seq=first_user.seq,
            message="用户消息: 第一轮",
            pre_run_checkpoint_id="cp-before-1",
            graph_thread_id="sess-1",
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
        second_user = await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="user",
            status="sent",
            content="第二轮",
        )
        await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=second_user.id,
            user_message_seq=second_user.seq,
            message="用户消息: 第二轮",
            pre_run_checkpoint_id="cp-before-2",
            graph_thread_id="sess-1",
        )
        await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="assistant",
            status="complete",
            content="第二轮回复",
        )
        await session.commit()

    async with fork_db() as session:
        result = await fork_agent_session_at_revision(
            session,
            source_session_id="sess-1",
            source_revision_id=first_revision.id,
            model_config={"max_context_tokens": 128000},
            new_session_id="sess-fork",
        )
        await session.commit()

    assert result.session_id == "sess-fork"
    assert result.task.title == "Agent Session(Fork)"
    assert result.state_values["session_id"] == "sess-fork"
    assert result.state_values["task_id"] == result.task.id
    assert result.state_values["current_revision_id"] is None

    async with fork_db() as session:
        fork_messages = await message_repo.list_by_session(session, "sess-fork")
        source_messages = await message_repo.list_by_session(session, "sess-1")
        fork_task = await session.get(Task, result.task.id)
        source_task = await session.get(Task, "task-1")

    assert [message.content for message in fork_messages] == ["第一轮", "第一轮回复"]
    assert [message.seq for message in fork_messages] == [0, 1]
    assert all("revision_id" not in message.metadata for message in fork_messages)
    assert fork_task is not None
    assert source_task is not None
    assert [message.content for message in source_messages] == [
        "第一轮",
        "第一轮回复",
        "第二轮",
        "第二轮回复",
    ]


@pytest.mark.asyncio
async def test_fork_copies_only_compactions_fully_inside_forked_message_range(fork_db):
    from app.agent_runtime.fork import fork_agent_session_at_revision
    from app.agent_runtime.persistence import compaction_repo
    from app.agent_runtime.revisions import begin_user_revision

    async with fork_db() as session:
        first_user = await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="user",
            status="sent",
            content="第一轮",
        )
        first_revision = await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=first_user.id,
            user_message_seq=first_user.seq,
            message="用户消息: 第一轮",
            pre_run_checkpoint_id="cp-before-1",
            graph_thread_id="sess-1",
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
        second_user = await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="user",
            status="sent",
            content="第二轮",
        )
        await begin_user_revision(
            session,
            project_id="proj-1",
            task_id="task-1",
            agent_session_id="sess-1",
            user_message_id=second_user.id,
            user_message_seq=second_user.seq,
            message="用户消息: 第二轮",
            pre_run_checkpoint_id="cp-before-2",
            graph_thread_id="sess-1",
        )
        await message_repo.insert_message(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            role="assistant",
            status="complete",
            content="第二轮回复",
        )
        await compaction_repo.insert_compaction(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            start_seq=0,
            end_seq=0,
            summary="完整落入 fork 范围",
            trigger="manual",
        )
        await compaction_repo.insert_compaction(
            session,
            session_id="sess-1",
            task_id="task-1",
            project_id="proj-1",
            start_seq=1,
            end_seq=2,
            summary="被 cutoff 截断",
            trigger="manual",
        )
        await session.commit()

    async with fork_db() as session:
        result = await fork_agent_session_at_revision(
            session,
            source_session_id="sess-1",
            source_revision_id=first_revision.id,
            model_config={"max_context_tokens": 128000},
            new_session_id="sess-fork",
        )
        await session.commit()

    async with fork_db() as session:
        rows = await compaction_repo.list_by_session(session, "sess-fork")

    assert [
        (row.session_id, row.task_id, row.start_seq, row.end_seq, row.summary)
        for row in rows
    ] == [
        (
            "sess-fork",
            result.task.id,
            0,
            0,
            "完整落入 fork 范围",
        ),
    ]
