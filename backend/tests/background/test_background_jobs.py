from collections import deque
from datetime import UTC, datetime, timedelta
import asyncio
import builtins
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from app.background.events.publisher import BackgroundEventPublisher
from app.background.events.types import EVENT_JOB_CANCELLED, EVENT_JOB_PROGRESS
from app.background.jobs.base import JobDefinition
from app.background.jobs.definitions import register_all_background_jobs
from app.background.jobs.definitions.chapter_summary import handle_chapter_summary
from app.background.jobs.definitions import summary_batch as summary_batch_definition
from app.background.jobs.constants import JOB_TYPE_SUMMARY_BATCH
from app.background.jobs.definitions.session_title import handle_session_title
from app.background.jobs import repos as job_repo
from app.background.jobs import service as background_service
from app.background.jobs.models import BackgroundJob, BackgroundJobItem
from app.background.jobs.states import (
    JOB_STATUS_FAILED,
    JOB_STATUS_CANCELLED,
    JOB_STATUS_CANCEL_REQUESTED,
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
    JOB_STATUS_SKIPPED,
    JOB_STATUS_TIMEOUT,
)
from app.background.runtime.context import JobCancelledError, JobContext
from app.background.runtime.dispatcher import dispatch_job
from app.background.runtime.registry import JobRegistry, get_job_registry
from app.background.runtime.worker import BackgroundWorker
from app.background.runtime.watchdog import BackgroundWatchdog
from app.background.transport.base import BackgroundTransport
from app.background.transport.messages import BackgroundEventMessage, JobNotification
from app.background.transport.zmq import ZmqBackgroundTransport
from app.memory.chapter import summary_service
from app.storage import database
from app.storage.models.chapter import Chapter
from app.storage.models.chapter_summary import ChapterSummary
from app.storage.models.project import Project
from app.storage.models.task import Task
from app.storage.models.volume import Volume
from app.storage.repos.chapter_summary_repo import (
    SUMMARY_STATUS_FAILED,
    SUMMARY_STATUS_QUEUED,
    SUMMARY_STATUS_READY,
    SUMMARY_STATUS_RUNNING,
)
from tests.model_registry import register_sqlmodel_models


def _default_volume_id(project: Project) -> str:
    return f"{project.id}-volume-1"


def _default_volume(project: Project, *, chapter_count: int = 1) -> Volume:
    return Volume(
        id=_default_volume_id(project),
        project_id=project.id,
        title="第一卷",
        order=1,
        chapter_count=chapter_count,
    )


async def _configure_file_database(tmp_path=None):
    register_sqlmodel_models()

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    database._async_session_factory = factory
    return engine, factory


class _NoopInput(BaseModel):
    value: str


async def _noop_handler(context: JobContext) -> dict[str, str]:
    return {"value": context.input["value"]}


async def _failing_handler(context: JobContext) -> None:
    raise RuntimeError("handler failed")


async def _slow_handler(context: JobContext) -> dict[str, str]:
    await asyncio.sleep(2)
    return {"value": context.input["value"]}


async def _persisting_handler(context: JobContext) -> dict[str, str]:
    await job_repo.create_item(
        context.session,
        BackgroundJobItem(
            job_id=context.job_id,
            item_key="persisted-item",
            type="test_item",
            status=JOB_STATUS_RUNNING,
            payload_json='{"ok": true}',
        ),
    )
    return {"value": "persisted"}


async def _failure_hook(context: JobContext, reason: str) -> None:
    await background_service.append_event(
        context.session,
        context.publisher,
        context.job,
        event_type="failure_hook_ran",
        payload={"reason": reason},
    )


class RecordingTransport(BackgroundTransport):
    def __init__(self) -> None:
        self.job_notifications: deque[JobNotification] = deque()
        self.events: deque[BackgroundEventMessage] = deque()

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def notify_job(self, message: JobNotification) -> None:
        self.job_notifications.append(message)

    async def receive_job(self, timeout_ms: int) -> JobNotification | None:
        if not self.job_notifications:
            return None
        return self.job_notifications.popleft()

    async def publish_event(self, message: BackgroundEventMessage) -> None:
        self.events.append(message)

    async def receive_event(self, timeout_ms: int) -> BackgroundEventMessage | None:
        if not self.events:
            return None
        return self.events.popleft()


class FailingEventTransport(RecordingTransport):
    async def publish_event(self, message: BackgroundEventMessage) -> None:
        raise RuntimeError("event transport unavailable")


class _FakeBackgroundSupervisor:
    def __init__(self, transport: RecordingTransport) -> None:
        self._publisher = BackgroundEventPublisher(transport)

    def create_event_publisher(self) -> BackgroundEventPublisher:
        return self._publisher


class _FakePubSocket:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    async def send_json(self, payload: dict[str, object]) -> None:
        self.messages.append(payload)


class _FakeSubSocket:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    async def recv_json(self) -> dict[str, object]:
        return self.payload


@pytest.fixture(autouse=True)
def reset_background_registry():
    original_session_factory = database._async_session_factory
    registry = get_job_registry()
    registry.clear()
    register_all_background_jobs()
    yield
    registry.clear()
    database._async_session_factory = original_session_factory


@pytest.mark.asyncio
async def test_submit_job_persists_background_job(session):
    project = Project(title="项目", description="")
    chapter = Chapter(project_id=project.id, volume_id=_default_volume_id(project), title="第一章", content="", word_count=0, order=1)
    task = Task(project_id=project.id, title="临时标题", mode="agent")
    session.add(project)
    session.add(_default_volume(project))
    session.add(chapter)
    session.add(task)
    await background_service.commit_and_notify(session)

    job = await background_service.submit_job(
        session,
        job_type="session_title",
        payload={"task_id": task.id, "seed_message": "写一场雨夜密谋"},
        context={"project_id": project.id, "model_policy": "light_model"},
        subject_type="task",
        subject_id=task.id,
    )
    await background_service.commit_and_notify(session)

    stored = await job_repo.get_job(session, job.id)
    assert stored is not None
    assert stored.type == "session_title"
    assert background_service.parse_json_object(stored.payload_json)["seed_message"] == "写一场雨夜密谋"
    assert stored.subject_type == "task"
    assert stored.subject_id == task.id
    assert stored.queue == "llm"
    assert stored.timeout_seconds == 90


@pytest.mark.asyncio
async def test_submit_job_defers_runtime_notification_until_after_commit(session, monkeypatch):
    notified_job_ids: list[str] = []

    async def notify_job_submitted(job_id: str) -> None:
        notified_job_ids.append(job_id)

    monkeypatch.setattr(background_service, "notify_job_submitted", notify_job_submitted)

    project = Project(title="项目", description="")
    chapter = Chapter(project_id=project.id, volume_id=_default_volume_id(project), title="第一章", content="", word_count=0, order=1)
    task = Task(project_id=project.id, title="临时标题", mode="agent")
    session.add(project)
    session.add(_default_volume(project))
    session.add(chapter)
    session.add(task)
    await session.commit()

    job = await background_service.submit_job(
        session,
        job_type="session_title",
        payload={"task_id": task.id, "seed_message": "写一场雨夜密谋"},
        context={"project_id": project.id, "model_policy": "light_model"},
        subject_type="task",
        subject_id=task.id,
    )

    assert notified_job_ids == []
    await session.commit()
    assert notified_job_ids == []

    await background_service.notify_submitted_jobs(session)
    assert notified_job_ids == [job.id]
    await background_service.notify_submitted_jobs(session)
    assert notified_job_ids == [job.id]


@pytest.mark.asyncio
async def test_submit_job_validates_definition_payload(session):
    with pytest.raises(ValueError):
        await background_service.submit_job(
            session,
            job_type="session_title",
            payload={"seed_message": "缺少 task_id"},
        )


@pytest.mark.asyncio
async def test_submit_job_lazy_loads_only_requested_definition(session, monkeypatch):
    get_job_registry().clear()
    original_import = builtins.__import__

    def import_without_chapter_summary(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "app.background.jobs.definitions.chapter_summary":
            raise AssertionError("chapter summary definition should not be imported")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", import_without_chapter_summary)

    job = await background_service.submit_job(
        session,
        job_type="session_title",
        payload={"task_id": "task-1", "seed_message": "hello"},
        context={"project_id": "project-1"},
        subject_type="task",
        subject_id="task-1",
    )

    assert job.type == "session_title"


def test_registry_rejects_duplicate_job_type():
    registry = JobRegistry()
    definition = JobDefinition(
        type="noop",
        name="Noop",
        description="Noop job",
        input_model=_NoopInput,
        handler=_noop_handler,
    )
    registry.register(definition)

    with pytest.raises(ValueError):
        registry.register(
            JobDefinition(
                type="noop",
                name="Other noop",
                description="Other noop job",
                input_model=_NoopInput,
                handler=_noop_handler,
            )
        )


def test_builtin_jobs_are_discoverable():
    definitions = {definition.type for definition in get_job_registry().list_definitions()}
    assert {"session_title", "chapter_summary", "long_term_summary"} <= definitions


@pytest.mark.asyncio
async def test_session_title_skips_when_light_model_missing(tmp_path):
    engine, factory = await _configure_file_database(tmp_path)
    session = factory()
    context: JobContext | None = None
    try:
        project = Project(title="项目", description="")
        chapter = Chapter(project_id=project.id, volume_id=_default_volume_id(project), title="第一章", content="", word_count=0, order=1)
        task = Task(project_id=project.id, title="临时标题", mode="agent")
        session.add(project)
        session.add(_default_volume(project))
        session.add(chapter)
        session.add(task)
        await session.commit()

        job = await background_service.submit_job(
            session,
            job_type="session_title",
            payload={"task_id": task.id, "seed_message": "写一场雨夜密谋"},
            context={"project_id": project.id, "model_policy": "light_model"},
            subject_type="task",
            subject_id=task.id,
        )
        job_id = job.id
        await session.commit()

        transport = RecordingTransport()
        context = JobContext(
            session=session,
            job=job,
            publisher=BackgroundEventPublisher(transport),
        )
        await handle_session_title(context)

        stored = await job_repo.get_job(context.session, job_id)
        assert stored is not None
        assert stored.status == JOB_STATUS_SKIPPED
    finally:
        if context is not None and context.session is not session:
            await context.session.close()
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_session_title_compiles_mentions_before_prompt_build(tmp_path):
    engine, factory = await _configure_file_database(tmp_path)
    session = factory()
    context: JobContext | None = None
    captured: dict[str, str] = {}
    try:
        project = Project(title="项目", description="")
        volume = _default_volume(project)
        chapter = Chapter(
            id="chapter-title-mentions",
            project_id=project.id,
            volume_id=volume.id,
            title="现章节标题",
            content="第一行\n第二行",
            word_count=2,
            order=1,
        )
        task = Task(project_id=project.id, title="临时标题", mode="agent")
        session.add(project)
        session.add(volume)
        session.add(chapter)
        session.add(task)
        await session.commit()

        job = await background_service.submit_job(
            session,
            job_type="session_title",
            payload={
                "task_id": task.id,
                "seed_message": (
                    '请基于<of-mention kind="chapter" chapter_id="chapter-title-mentions" label="旧章节" />'
                    '和<of-mention kind="line_range" chapter_id="chapter-title-mentions" start_line="4" '
                    'end_line="9" label="旧片段">保留快照</of-mention>命名'
                ),
            },
            context={"project_id": project.id, "model_policy": "light_model"},
            subject_type="task",
            subject_id=task.id,
        )
        await session.commit()

        transport = RecordingTransport()
        context = JobContext(
            session=session,
            job=job,
            publisher=BackgroundEventPublisher(transport),
        )

        compiled_text = '请基于\n> 引用章节：现章节标题\n和\n> 引用片段：现章节标题 第4-9行；原文快照：保留快照\n命名'

        async def fake_build_chat_messages(_session, *, runtime, **_kwargs):
            captured["current_message"] = runtime.current_message
            return []

        fake_resolved = SimpleNamespace(
            client=SimpleNamespace(
                generate=AsyncMock(return_value=SimpleNamespace(content="标题测试")),
            )
        )

        with patch(
            "app.background.jobs.definitions.session_title.resolve_background_llm",
            AsyncMock(return_value=fake_resolved),
        ), patch(
            "app.background.jobs.definitions.session_title.compile_canonical_mentions",
            AsyncMock(return_value=compiled_text),
        ), patch(
            "app.background.jobs.definitions.session_title.build_chat_messages",
            AsyncMock(side_effect=fake_build_chat_messages),
        ):
            result = await handle_session_title(context)

        assert captured["current_message"] == compiled_text
        assert result == {"title": "标题测试", "task_id": task.id}
    finally:
        if context is not None and context.session is not session:
            await context.session.close()
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_dispatch_job_keeps_handler_writes_after_cancel_check(tmp_path):
    engine, factory = await _configure_file_database(tmp_path)
    session = factory()
    try:
        get_job_registry().register(
            JobDefinition(
                type="persisting_job",
                name="Persisting job",
                description="Persists an item before returning.",
                input_model=_NoopInput,
                handler=_persisting_handler,
            )
        )
        job = await background_service.submit_job(
            session,
            job_type="persisting_job",
            payload={"value": "x"},
            context={"project_id": "project-1"},
            subject_type="project",
            subject_id="project-1",
        )
        job.status = JOB_STATUS_RUNNING
        await session.commit()

        transport = RecordingTransport()
        context = JobContext(
            session=session,
            job=job,
            publisher=BackgroundEventPublisher(transport),
        )
        with patch.object(JobContext, "check_cancelled", new_callable=AsyncMock):
            result = await dispatch_job(context)
        await session.commit()

        items = await job_repo.list_items(session, job_id=job.id)
        assert result == {"value": "persisted"}
        assert len(items) == 1
        assert items[0].item_key == "persisted-item"
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_publisher_does_not_commit(session):
    job = await job_repo.create_job(
        session,
        BackgroundJob(type="unknown", payload_json="{}"),
    )
    publisher = BackgroundEventPublisher(None)

    await publisher.publish(session, job=job, event_type="test_event")
    await session.rollback()

    stored = await job_repo.get_job(session, job.id)
    assert stored is None


@pytest.mark.asyncio
async def test_pending_job_cancel_marks_cancelled(session):
    job = await job_repo.create_job(
        session,
        BackgroundJob(type="unknown", payload_json="{}"),
    )

    job = await background_service.request_cancel(
        session,
        BackgroundEventPublisher(None),
        job,
        reason="用户取消",
    )
    await session.commit()

    assert job.status == JOB_STATUS_CANCELLED
    assert job.cancel_reason == "用户取消"


@pytest.mark.asyncio
async def test_pending_job_cancel_publishes_transport_event(session):
    transport = RecordingTransport()
    job = await job_repo.create_job(
        session,
        BackgroundJob(type="unknown", payload_json="{}", subject_type="task", subject_id="task-1"),
    )

    job = await background_service.request_cancel(
        session,
        BackgroundEventPublisher(transport),
        job,
        reason="用户取消",
    )
    await background_service.commit_and_notify(session)

    assert job.status == JOB_STATUS_CANCELLED
    assert len(transport.events) == 1
    event = transport.events[0]
    assert event.type == EVENT_JOB_CANCELLED
    assert event.job_id == job.id
    assert event.job_type == job.type
    assert event.item_type is None
    assert event.subject_type == "task"
    assert event.subject_id == "task-1"


@pytest.mark.asyncio
async def test_event_transport_publish_is_discarded_on_rollback(session):
    transport = RecordingTransport()
    job = await job_repo.create_job(
        session,
        BackgroundJob(type="unknown", payload_json="{}", subject_type="task", subject_id="task-1"),
    )
    publisher = BackgroundEventPublisher(transport)

    await publisher.publish(session, job=job, event_type=EVENT_JOB_CANCELLED)
    assert len(transport.events) == 0

    await background_service.rollback_and_discard(session)
    assert len(transport.events) == 0


@pytest.mark.asyncio
async def test_commit_and_notify_keeps_commit_when_event_transport_fails(session):
    transport = FailingEventTransport()
    job = await job_repo.create_job(
        session,
        BackgroundJob(type="unknown", payload_json="{}", subject_type="task", subject_id="task-1"),
    )
    publisher = BackgroundEventPublisher(transport)

    await publisher.publish(session, job=job, event_type=EVENT_JOB_CANCELLED)
    await background_service.commit_and_notify(session)

    stored = await job_repo.get_job(session, job.id)
    events = await job_repo.list_events(session, job_id=job.id)
    assert stored is not None
    assert len(events) == 1


@pytest.mark.asyncio
async def test_next_event_sequence_uses_job_counter(session):
    job = await job_repo.create_job(
        session,
        BackgroundJob(type="unknown", payload_json="{}"),
    )

    first = await job_repo.next_event_sequence(session, job.id)
    second = await job_repo.next_event_sequence(session, job.id)
    await session.commit()

    stored = await job_repo.get_job(session, job.id)
    assert first == 1
    assert second == 2
    assert stored is not None
    assert stored.event_sequence == 2


@pytest.mark.asyncio
async def test_check_cancelled_reads_latest_state_from_short_session(tmp_path):
    engine, factory = await _configure_file_database(tmp_path)
    session = factory()
    context: JobContext | None = None
    try:
        job = await job_repo.create_job(
            session,
            BackgroundJob(type="unknown", status=JOB_STATUS_RUNNING, payload_json="{}"),
        )
        job_id = job.id
        await session.commit()
        await session.execute(select(BackgroundJob).where(BackgroundJob.id == job_id))

        cancel_session = factory()
        try:
            latest = await job_repo.get_job(cancel_session, job_id)
            assert latest is not None
            latest.status = JOB_STATUS_CANCEL_REQUESTED
            latest.cancel_reason = "用户取消"
            await job_repo.save_job(cancel_session, latest)
            await cancel_session.commit()
        finally:
            await cancel_session.close()

        context = JobContext(session=session, job=job, publisher=BackgroundEventPublisher(None))
        with pytest.raises(JobCancelledError):
            await context.check_cancelled()
        assert context.job_id == job_id
        assert context.input == {}
    finally:
        if context is not None and context.session is not session:
            await context.session.close()
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_chapter_summary_skips_when_light_model_missing(tmp_path):
    engine, factory = await _configure_file_database(tmp_path)
    session = factory()
    context: JobContext | None = None
    try:
        project = Project(title="项目", description="")
        chapter = Chapter(project_id=project.id, volume_id=_default_volume_id(project), title="第一章", content="正文", word_count=2, order=1)
        session.add(project)
        session.add(_default_volume(project))
        session.add(chapter)
        await session.commit()

        job = await background_service.submit_job(
            session,
            job_type="chapter_summary",
            payload={"chapter_id": chapter.id},
            context={"project_id": project.id, "model_policy": "light_model"},
            subject_type="project",
            subject_id=project.id,
        )
        job_id = job.id
        await session.commit()

        transport = RecordingTransport()
        context = JobContext(
            session=session,
            job=job,
            publisher=BackgroundEventPublisher(transport),
        )
        result = await handle_chapter_summary(context)

        stored = await job_repo.get_job(context.session, job_id)
        assert result is None
        assert stored is not None
        assert stored.status == JOB_STATUS_SKIPPED
    finally:
        if context is not None and context.session is not session:
            await context.session.close()
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_worker_runs_failure_hook_after_rollback(tmp_path):
    engine, factory = await _configure_file_database(tmp_path)
    session = factory()
    try:
        get_job_registry().register(
            JobDefinition(
                type="failing_job",
                name="Failing job",
                description="Fails for lifecycle hook coverage.",
                input_model=_NoopInput,
                handler=_failing_handler,
                on_failed=_failure_hook,
            )
        )
        job = await job_repo.create_job(
            session,
            BackgroundJob(type="failing_job", payload_json='{"value":"x"}'),
        )
        await background_service.commit_and_notify(session)

        transport = RecordingTransport()
        worker = BackgroundWorker(worker_id="worker-1", transport=transport, scan_interval_seconds=1)
        with patch.object(JobContext, "check_cancelled", new_callable=AsyncMock):
            await worker._run_job(job.id)

        job_id = job.id
        session.expire(job)
        await session.refresh(job)
        stored = await job_repo.get_job(session, job_id)
        events = await job_repo.list_events(session, job_id=job_id)
        assert stored is not None
        assert stored.status == "failed"
        assert any(event.event_type == "failure_hook_ran" for event in events)
        assert any(event.type == "failure_hook_ran" for event in transport.events)
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_summary_batch_failure_hook_marks_incomplete_items_failed(tmp_path, monkeypatch):
    engine, factory = await _configure_file_database(tmp_path)
    session = factory()
    try:
        project = Project(title="项目", description="")
        chapter = Chapter(project_id=project.id, volume_id=_default_volume_id(project), title="第一章", content="正文" * 400, word_count=800, order=1)
        session.add(project)
        session.add(_default_volume(project))
        session.add(chapter)
        await session.commit()

        summary = ChapterSummary(
            project_id=project.id,
            summary_type="chapter",
            status=SUMMARY_STATUS_QUEUED,
            chapter_id=chapter.id,
            chapter_order=chapter.order,
            start_order=chapter.order,
            end_order=chapter.order,
        )
        session.add(summary)
        await session.commit()

        job = await background_service.submit_job(
            session,
            job_type="summary_batch",
            payload={"project_id": project.id},
            context={"project_id": project.id, "model_policy": "light_model"},
            subject_type="project",
            subject_id=project.id,
        )
        job_id = job.id
        item = await background_service.create_item(
            session,
            job_id=job_id,
            item_key=f"chapter:{chapter.id}",
            item_type="chapter_summary",
            payload={"project_id": project.id, "chapter_id": chapter.id},
            order_index=0,
        )
        item_id = item.id
        summary_id = summary.id
        summary.job_id = item.id
        await session.commit()

        async def fail_mark_item_running(_session, _item):
            raise RuntimeError("batch crashed before item start")

        monkeypatch.setattr(summary_batch_definition, "_mark_item_running", fail_mark_item_running)

        transport = RecordingTransport()
        worker = BackgroundWorker(worker_id="worker-1", transport=transport, scan_interval_seconds=1)
        await worker._run_job(job_id)

        verification_session = factory()
        try:
            stored_job = await job_repo.get_job(verification_session, job_id)
            stored_item = await verification_session.get(BackgroundJobItem, item_id)
            stored_summary = await verification_session.get(ChapterSummary, summary_id)
        finally:
            await verification_session.close()
        assert stored_job is not None
        assert stored_item is not None
        assert stored_summary is not None
        assert stored_job.status == JOB_STATUS_FAILED
        assert stored_item.status == JOB_STATUS_FAILED
        assert stored_summary.status == SUMMARY_STATUS_FAILED
        assert stored_summary.error_message == "batch crashed before item start"
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_summary_batch_publishes_chapter_update_without_loading_job_id(tmp_path, monkeypatch):
    engine, factory = await _configure_file_database(tmp_path)
    session = factory()
    try:
        project = Project(title="项目", description="")
        chapter = Chapter(project_id=project.id, volume_id=_default_volume_id(project), title="第一章", content="正文" * 400, word_count=800, order=1)
        session.add(project)
        session.add(_default_volume(project))
        session.add(chapter)
        await session.commit()

        job = await background_service.submit_job(
            session,
            job_type="summary_batch",
            payload={"project_id": project.id},
            context={"project_id": project.id, "model_policy": "light_model"},
            subject_type="project",
            subject_id=project.id,
        )
        await session.commit()

        transport = RecordingTransport()
        context = JobContext(
            session=session,
            job=job,
            publisher=BackgroundEventPublisher(transport),
        )
        row = ChapterSummary(
            project_id=project.id,
            summary_type="chapter",
            status=SUMMARY_STATUS_FAILED,
            chapter_id=chapter.id,
            chapter_order=chapter.order,
            start_order=chapter.order,
            end_order=chapter.order,
        )
        session.add(row)
        await session.flush()

        class ExplodingJob:
            @property
            def id(self):
                raise AssertionError("should not access ORM job.id during publish")

            @property
            def type(self):
                raise AssertionError("should not access ORM job.type during publish")

            @property
            def subject_type(self):
                raise AssertionError("should not access ORM job.subject_type during publish")

            @property
            def subject_id(self):
                raise AssertionError("should not access ORM job.subject_id during publish")

        context.job = ExplodingJob()

        await summary_batch_definition.summary_service.publish_chapter_summary_update(context, row)
        await background_service.commit_and_notify(session)
        assert len(transport.events) == 1
        assert transport.events[0].job_type == JOB_TYPE_SUMMARY_BATCH
        events = await job_repo.list_events(session, job_id=context.job_id)
        assert any(event.event_type == "chapter_summary_updated" for event in events)
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_summary_batch_publishes_chapter_update_with_item_type(tmp_path):
    engine, factory = await _configure_file_database(tmp_path)
    session = factory()
    try:
        project = Project(title="项目", description="")
        chapter = Chapter(project_id=project.id, volume_id=_default_volume_id(project), title="第一章", content="正文", word_count=2, order=1)
        session.add(project)
        session.add(_default_volume(project))
        session.add(chapter)
        await session.commit()

        job = await background_service.submit_job(
            session,
            job_type="summary_batch",
            payload={"project_id": project.id},
            context={"project_id": project.id, "model_policy": "light_model"},
            subject_type="project",
            subject_id=project.id,
        )
        await session.commit()

        transport = RecordingTransport()
        publisher = BackgroundEventPublisher(transport)
        context = JobContext(session=session, job=job, publisher=publisher)
        row = ChapterSummary(
            project_id=project.id,
            summary_type="chapter",
            status=SUMMARY_STATUS_FAILED,
            chapter_id=chapter.id,
            chapter_order=chapter.order,
            start_order=chapter.order,
            end_order=chapter.order,
            error_message="生成失败",
        )
        session.add(row)
        await session.flush()

        await summary_batch_definition.summary_service.publish_chapter_summary_update(context, row)
        await background_service.commit_and_notify(session)
        assert len(transport.events) == 1
        event = transport.events[0]
        assert event.job_type == JOB_TYPE_SUMMARY_BATCH
        assert event.item_type == "chapter_summary"
        assert event.payload["is_stale"] is False
        assert event.payload["progress_message"] is None
        assert event.payload["error_message"] == "生成失败"
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_append_summary_batch_items_publish_queued_item_events(tmp_path, monkeypatch):
    engine, factory = await _configure_file_database(tmp_path)
    session = factory()
    try:
        project = Project(title="项目", description="")
        chapters = [
            Chapter(
                project_id=project.id,
                volume_id=_default_volume_id(project),
                title=f"第{index + 1}章",
                content="正文" * 400,
                word_count=800,
                order=index + 1,
            )
            for index in range(11)
        ]
        session.add(project)
        session.add(_default_volume(project, chapter_count=len(chapters)))
        session.add_all(chapters)
        await session.commit()

        for chapter in chapters[:10]:
            session.add(
                ChapterSummary(
                    project_id=project.id,
                    summary_type="chapter",
                    status=SUMMARY_STATUS_READY,
                    chapter_id=chapter.id,
                    chapter_order=chapter.order,
                    start_order=chapter.order,
                    end_order=chapter.order,
                    summary=f"第{chapter.order}章摘要",
                    source_content_normalized=summary_service.normalize_summary_source_content(chapter.content),
                )
            )
        await session.commit()

        transport = RecordingTransport()
        monkeypatch.setattr(
            summary_service,
            "get_background_supervisor",
            lambda: _FakeBackgroundSupervisor(transport),
            raising=False,
        )

        chapter_result = await summary_service.append_chapter_summary_items(
            session,
            project.id,
            [chapters[10].id],
        )
        long_term_result = await summary_service.append_long_term_summary_items(
            session,
            project.id,
            [(1, 10)],
        )
        await background_service.commit_and_notify(session)

        queued_events = [event for event in transport.events if event.type == "background_item_queued"]
        assert len(queued_events) == 2
        chapter_event = next(event for event in queued_events if event.item_type == "chapter_summary")
        long_term_event = next(event for event in queued_events if event.item_type == "long_term_summary")

        assert chapter_event.job_type == JOB_TYPE_SUMMARY_BATCH
        assert chapter_event.item_id == chapter_result.item_ids[0]
        assert chapter_event.payload["project_id"] == project.id
        assert chapter_event.payload["chapter_id"] == chapters[10].id
        assert chapter_event.payload["summary_id"] == chapter_result.chapter_summary_ids[0]
        assert chapter_event.payload["status"] == "queued"
        assert chapter_event.payload["is_stale"] is False
        assert chapter_event.payload["progress_current"] == 0
        assert chapter_event.payload["progress_total"] == 3
        assert chapter_event.payload["progress_message"] == "已加入队列"
        assert chapter_event.payload["error_message"] is None

        assert long_term_event.job_type == JOB_TYPE_SUMMARY_BATCH
        assert long_term_event.item_id == long_term_result.item_ids[0]
        assert long_term_event.payload["project_id"] == project.id
        assert long_term_event.payload["start_order"] == 1
        assert long_term_event.payload["end_order"] == 10
        assert long_term_event.payload["summary_id"] == long_term_result.long_term_summary_ids[0]
        assert long_term_event.payload["status"] == "queued"
        assert long_term_event.payload["is_stale"] is False
        assert long_term_event.payload["progress_current"] == 0
        assert long_term_event.payload["progress_total"] == 3
        assert long_term_event.payload["progress_message"] == "已加入队列"
        assert long_term_event.payload["error_message"] is None
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_zmq_background_transport_serializes_event_job_and_item_types():
    transport = ZmqBackgroundTransport("inproc://job", "inproc://event")
    pub = _FakePubSocket()
    transport._event_pub = pub

    message = BackgroundEventMessage(
        type="chapter_summary_updated",
        job_id="job-1",
        job_type="summary_batch",
        item_id="item-1",
        item_type="chapter_summary",
        subject_type="project",
        subject_id="project-1",
        payload={"ok": True},
        created_at="2026-05-23T10:00:00+08:00",
        project_revision=123456789,
    )
    await transport.publish_event(message)
    assert pub.messages[0]["project_revision"] == 123456789

    transport._event_sub = _FakeSubSocket(pub.messages[0])
    transport._poll = lambda _socket, _timeout_ms: asyncio.sleep(0, result=True)  # type: ignore[assignment]
    round_trip = await transport.receive_event(1)
    assert round_trip is not None
    assert round_trip.job_type == "summary_batch"
    assert round_trip.item_type == "chapter_summary"
    assert round_trip.project_revision == 123456789

    transport._event_sub = _FakeSubSocket(
        {
            "type": "chapter_summary_updated",
            "job_id": "job-2",
            "payload": {"ok": True},
            "created_at": "2026-05-23T10:00:00+08:00",
        }
    )
    legacy = await transport.receive_event(1)
    assert legacy is not None
    assert legacy.job_type == "unknown"
    assert legacy.item_type is None
    assert legacy.project_revision is None


@pytest.mark.asyncio
async def test_summary_batch_commits_after_each_item(tmp_path, monkeypatch):
    engine, factory = await _configure_file_database(tmp_path)
    session = factory()
    try:
        project = Project(title="项目", description="")
        chapter_one = Chapter(project_id=project.id, volume_id=_default_volume_id(project), title="第一章", content="正文" * 400, word_count=800, order=1)
        chapter_two = Chapter(project_id=project.id, volume_id=_default_volume_id(project), title="第二章", content="正文" * 400, word_count=800, order=2)
        session.add(project)
        session.add(_default_volume(project, chapter_count=2))
        session.add(chapter_one)
        session.add(chapter_two)
        await session.commit()

        job = await background_service.submit_job(
            session,
            job_type="summary_batch",
            payload={"project_id": project.id},
            context={"project_id": project.id, "model_policy": "light_model"},
            subject_type="project",
            subject_id=project.id,
        )
        job_id = job.id
        await background_service.create_item(
            session,
            job_id=job_id,
            item_key=f"chapter:{chapter_one.id}",
            item_type="chapter_summary",
            payload={"project_id": project.id, "chapter_id": chapter_one.id},
            order_index=0,
        )
        await background_service.create_item(
            session,
            job_id=job_id,
            item_key=f"chapter:{chapter_two.id}",
            item_type="chapter_summary",
            payload={"project_id": project.id, "chapter_id": chapter_two.id},
            order_index=1,
        )
        await session.commit()

        processed: list[str] = []

        async def fake_process(context, item, metadata):
            _ = metadata
            processed.append(item.id)
            item.status = JOB_STATUS_SKIPPED
            await summary_batch_definition._save_item(context.session, item)

        commit_count = 0
        original_commit_and_notify = background_service.commit_and_notify

        async def counting_commit_and_notify(commit_session):
            nonlocal commit_count
            commit_count += 1
            await original_commit_and_notify(commit_session)

        monkeypatch.setattr(summary_batch_definition, "_process_chapter_item", fake_process)
        monkeypatch.setattr(background_service, "commit_and_notify", counting_commit_and_notify)

        transport = RecordingTransport()
        worker = BackgroundWorker(worker_id="worker-1", transport=transport, scan_interval_seconds=1)
        await worker._run_job(job_id)

        assert len(processed) == 2
        assert commit_count >= 3
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_summary_batch_persists_running_status_before_generation(tmp_path, monkeypatch):
    engine, factory = await _configure_file_database(tmp_path)
    session = factory()
    try:
        project = Project(title="项目", description="")
        chapter = Chapter(project_id=project.id, volume_id=_default_volume_id(project), title="第一章", content="正文" * 400, word_count=800, order=1)
        session.add(project)
        session.add(_default_volume(project))
        session.add(chapter)
        await session.commit()

        result = await summary_service.append_chapter_summary_items(
            session,
            project.id,
            [chapter.id],
        )
        await session.commit()

        observed_statuses: list[str] = []

        async def fake_build_prompt(_session, chapter_id: str):
            verification_session = factory()
            try:
                row = await summary_service.get_chapter_summary(verification_session, chapter_id)
                assert row is not None
                observed_statuses.append(row.status)
            finally:
                await verification_session.close()
            return "prompt"

        class FakeChapterSummaryResult:
            start_time = "开始"
            end_time = "结束"
            characters = ["角色A"]
            locations = ["地点A"]
            summary = "章节摘要"
            token_count = 12

        async def fake_generate(_client, _prompt):
            return FakeChapterSummaryResult()

        class FakeResolvedModel:
            id = "test-model"

        class FakeResolved:
            model = FakeResolvedModel()
            client = object()

        async def fake_resolve_background_llm(_session, model_policy: str, model_id: str | None):
            _ = (model_policy, model_id)
            return FakeResolved()

        monkeypatch.setattr(summary_batch_definition, "resolve_background_llm", fake_resolve_background_llm)
        monkeypatch.setattr(summary_batch_definition.summary_generator, "build_chapter_summary_prompt", fake_build_prompt)
        monkeypatch.setattr(summary_batch_definition.summary_generator, "generate_chapter_summary_from_prompt", fake_generate)

        transport = RecordingTransport()
        worker = BackgroundWorker(worker_id="worker-1", transport=transport, scan_interval_seconds=1)
        await worker._run_job(result.batch_job_id)

        assert observed_statuses == [SUMMARY_STATUS_RUNNING]
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_summary_batch_progress_event_contains_aggregated_batch_progress(tmp_path, monkeypatch):
    engine, factory = await _configure_file_database(tmp_path)
    session = factory()
    try:
        project = Project(title="项目", description="")
        chapter = Chapter(project_id=project.id, volume_id=_default_volume_id(project), title="第一章", content="正文" * 400, word_count=800, order=1)
        session.add(project)
        session.add(_default_volume(project))
        session.add(chapter)
        await session.commit()

        result = await summary_service.append_chapter_summary_items(session, project.id, [chapter.id])
        await session.commit()

        class FakeChapterSummaryResult:
            start_time = "开始"
            end_time = "结束"
            characters = ["角色A"]
            locations = ["地点A"]
            summary = "章节摘要"
            token_count = 12

        async def fake_resolve_background_llm(_session, model_policy: str, model_id: str | None):
            class FakeResolvedModel:
                id = "test-model"

            class FakeResolved:
                model = FakeResolvedModel()
                client = object()

            _ = (model_policy, model_id)
            return FakeResolved()

        async def fake_build_prompt(_session, _chapter_id: str):
            return "prompt"

        async def fake_generate(_client, _prompt):
            return FakeChapterSummaryResult()

        monkeypatch.setattr(summary_batch_definition, "resolve_background_llm", fake_resolve_background_llm)
        monkeypatch.setattr(summary_batch_definition.summary_generator, "build_chapter_summary_prompt", fake_build_prompt)
        monkeypatch.setattr(summary_batch_definition.summary_generator, "generate_chapter_summary_from_prompt", fake_generate)

        transport = RecordingTransport()
        worker = BackgroundWorker(worker_id="worker-1", transport=transport, scan_interval_seconds=1)
        await worker._run_job(result.batch_job_id)

        progress_events = [event for event in transport.events if event.type == EVENT_JOB_PROGRESS]
        assert progress_events
        generating_event = next(
            event for event in progress_events if event.payload.get("message") == "正在生成章节摘要"
        )
        assert generating_event.payload["current"] == 1
        assert generating_event.payload["total"] == 3
        assert generating_event.payload["progress_percent"] == 33
        assert generating_event.payload["total_item_count"] == 1
        assert generating_event.payload["completed_item_count"] == 0
        assert generating_event.payload["running_item_count"] == 1
        assert generating_event.payload["queued_item_count"] == 0
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_summary_batch_emits_item_progress_and_terminal_events(tmp_path, monkeypatch):
    engine, factory = await _configure_file_database(tmp_path)
    session = factory()
    try:
        project = Project(title="项目", description="")
        chapter = Chapter(project_id=project.id, volume_id=_default_volume_id(project), title="第一章", content="正文" * 400, word_count=800, order=1)
        session.add(project)
        session.add(_default_volume(project))
        session.add(chapter)
        await session.commit()

        result = await summary_service.append_chapter_summary_items(session, project.id, [chapter.id])
        await session.commit()

        class FakeChapterSummaryResult:
            start_time = "开始"
            end_time = "结束"
            characters = ["角色A"]
            locations = ["地点A"]
            summary = "章节摘要"
            token_count = 12

        async def fake_resolve_background_llm(_session, model_policy: str, model_id: str | None):
            class FakeResolvedModel:
                id = "test-model"

            class FakeResolved:
                model = FakeResolvedModel()
                client = object()

            _ = (model_policy, model_id)
            return FakeResolved()

        async def fake_build_prompt(_session, _chapter_id: str):
            return "prompt"

        async def fake_generate(_client, _prompt):
            return FakeChapterSummaryResult()

        monkeypatch.setattr(summary_batch_definition, "resolve_background_llm", fake_resolve_background_llm)
        monkeypatch.setattr(summary_batch_definition.summary_generator, "build_chapter_summary_prompt", fake_build_prompt)
        monkeypatch.setattr(summary_batch_definition.summary_generator, "generate_chapter_summary_from_prompt", fake_generate)

        transport = RecordingTransport()
        worker = BackgroundWorker(worker_id="worker-1", transport=transport, scan_interval_seconds=1)
        await worker._run_job(result.batch_job_id)

        item_progress_events = [
            event for event in transport.events if event.type == "background_item_progress"
        ]
        assert item_progress_events
        generating_event = next(
            event for event in item_progress_events if event.payload["progress_message"] == "正在生成章节摘要"
        )
        assert generating_event.item_type == "chapter_summary"
        assert generating_event.payload["project_id"] == project.id
        assert generating_event.payload["chapter_id"] == chapter.id
        assert generating_event.payload["summary_id"] == result.chapter_summary_ids[0]
        assert generating_event.payload["status"] == "running"
        assert generating_event.payload["is_stale"] is False
        assert generating_event.payload["progress_current"] == 1
        assert generating_event.payload["progress_total"] == 3
        assert generating_event.payload["error_message"] is None

        terminal_event = next(
            event for event in transport.events if event.type == "background_item_succeeded"
        )
        assert terminal_event.item_type == "chapter_summary"
        assert terminal_event.item_id == result.item_ids[0]
        assert terminal_event.payload["project_id"] == project.id
        assert terminal_event.payload["chapter_id"] == chapter.id
        assert terminal_event.payload["summary_id"] == result.chapter_summary_ids[0]
        assert terminal_event.payload["status"] == "succeeded"
        assert terminal_event.payload["is_stale"] is False
        assert terminal_event.payload["progress_current"] == 3
        assert terminal_event.payload["progress_total"] == 3
        assert terminal_event.payload["progress_message"] == "章节摘要完成"
        assert terminal_event.payload["error_message"] is None
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_summary_batch_progress_treats_pending_items_as_zero_progress(tmp_path):
    engine, factory = await _configure_file_database(tmp_path)
    session = factory()
    try:
        job = BackgroundJob(
            id="job-summary-pending",
            type="summary_batch",
            status="running",
            subject_type="project",
            subject_id="project-1",
            payload_json='{"project_id":"project-1"}',
            context_json='{"project_id":"project-1"}',
            progress_json="{}",
        )
        session.add(job)
        session.add(
            BackgroundJobItem(
                id="item-summary-pending",
                job_id=job.id,
                item_key="chapter:chapter-1",
                type="chapter_summary",
                status=JOB_STATUS_PENDING,
                payload_json='{"chapter_id":"chapter-1"}',
                progress_json='{"current":0,"total":3,"message":"已加入队列"}',
                order_index=0,
            )
        )
        await session.commit()

        payload = summary_batch_definition._build_batch_progress_payload(
            job,
            await background_service.list_job_items(session, job_id=job.id),
            message="已加入队列",
        )

        assert payload["current"] == 0
        assert payload["progress_percent"] == 0
        assert payload["queued_item_count"] == 1
        assert payload["running_item_count"] == 0
        assert payload["completed_item_count"] == 0
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_append_chapter_summary_items_keeps_ready_summary_ready(tmp_path):
    engine, factory = await _configure_file_database(tmp_path)
    session = factory()
    try:
        project = Project(title="项目", description="")
        chapter = Chapter(project_id=project.id, volume_id=_default_volume_id(project), title="第一章", content="正文" * 400, word_count=800, order=1)
        session.add(project)
        session.add(_default_volume(project))
        session.add(chapter)
        await session.commit()

        summary = ChapterSummary(
            project_id=project.id,
            summary_type="chapter",
            status="ready",
            chapter_id=chapter.id,
            chapter_order=chapter.order,
            start_order=chapter.order,
            end_order=chapter.order,
            summary="已完成摘要",
            source_content_normalized=summary_service.normalize_summary_source_content(chapter.content),
        )
        session.add(summary)
        await session.commit()

        result = await summary_service.append_chapter_summary_items(
            session,
            project.id,
            [chapter.id],
        )
        await session.commit()

        stored_summary = await session.get(ChapterSummary, summary.id)
        items = await background_service.list_job_items(session, job_id=result.batch_job_id)
        assert stored_summary is not None
        assert stored_summary.status == "ready"
        assert result.item_ids == []
        assert len(items) == 0
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_append_chapter_summary_items_creates_item_for_stale_ready_without_downgrading(tmp_path):
    engine, factory = await _configure_file_database(tmp_path)
    session = factory()
    try:
        project = Project(title="项目", description="")
        chapter = Chapter(project_id=project.id, volume_id=_default_volume_id(project), title="第一章", content="新正文" * 400, word_count=800, order=1)
        session.add(project)
        session.add(_default_volume(project))
        session.add(chapter)
        await session.commit()

        summary = ChapterSummary(
            project_id=project.id,
            summary_type="chapter",
            status="ready",
            chapter_id=chapter.id,
            chapter_order=chapter.order,
            start_order=chapter.order,
            end_order=chapter.order,
            summary="旧摘要",
            source_content_normalized="旧正文",
        )
        session.add(summary)
        await session.commit()

        result = await summary_service.append_chapter_summary_items(
            session,
            project.id,
            [chapter.id],
        )
        await session.commit()

        stored_summary = await session.get(ChapterSummary, summary.id)
        items = await background_service.list_job_items(session, job_id=result.batch_job_id)
        assert stored_summary is not None
        assert stored_summary.status == "ready"
        assert len(result.item_ids) == 1
        assert len(items) == 1
        assert items[0].type == "chapter_summary"
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_worker_heartbeats_running_job_while_handler_is_active(tmp_path):
    engine, factory = await _configure_file_database(tmp_path)
    session = factory()
    get_job_registry().register(
        JobDefinition(
            type="slow_job",
            name="Slow job",
            description="Runs long enough to need heartbeat.",
            input_model=_NoopInput,
            handler=_slow_handler,
        )
    )
    try:
        job = await job_repo.create_job(
            session,
            BackgroundJob(
                type="slow_job",
                payload_json='{"value":"x"}',
                timeout_seconds=3,
                max_attempts=1,
            ),
        )
        job_id = job.id
        await background_service.commit_and_notify(session)

        transport = RecordingTransport()
        worker = BackgroundWorker(worker_id="worker-1", transport=transport, scan_interval_seconds=1)
        run_task = asyncio.create_task(worker._run_job(job_id))
        try:
            await asyncio.sleep(1.4)

            verify_session = factory()
            try:
                result = await verify_session.execute(
                    select(BackgroundJob).where(BackgroundJob.id == job_id)
                )
                running_job = result.scalar_one()
                assert running_job.status == JOB_STATUS_RUNNING
                assert running_job.heartbeat_at is not None
                assert running_job.heartbeat_at > running_job.locked_at
            finally:
                await verify_session.close()

            await run_task
        finally:
            if not run_task.done():
                run_task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await run_task
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_watchdog_does_not_recover_job_with_active_heartbeat(session):
    database._async_session_factory = sessionmaker(
        session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    now = datetime.now(UTC)
    job = await job_repo.create_job(
        session,
        BackgroundJob(
            type="unknown",
            status="running",
            payload_json="{}",
            attempt_count=1,
            max_attempts=2,
            locked_by="worker-1",
            locked_at=now - timedelta(minutes=10),
            heartbeat_at=now,
            lease_expires_at=now + timedelta(seconds=30),
        ),
    )
    await session.commit()

    watchdog = BackgroundWatchdog(transport=None, interval_seconds=1)
    recovered_count = await watchdog.run_once()

    await session.refresh(job)
    stored = await job_repo.get_job(session, job.id)
    assert recovered_count == 0
    assert stored is not None
    assert stored.status == JOB_STATUS_RUNNING
    assert stored.locked_by == "worker-1"


@pytest.mark.asyncio
async def test_claim_job_only_succeeds_once(session):
    job = await job_repo.create_job(
        session,
        BackgroundJob(type="unknown", payload_json="{}"),
    )
    await session.commit()

    first = await job_repo.claim_job(
        session,
        job_id=job.id,
        worker_id="worker-1",
        lease_seconds=60,
    )
    second = await job_repo.claim_job(
        session,
        job_id=job.id,
        worker_id="worker-2",
        lease_seconds=60,
    )
    await session.commit()

    assert first is not None
    assert first.status == JOB_STATUS_RUNNING
    assert first.locked_by == "worker-1"
    assert first.attempt_count == 1
    assert second is None

    stored = await job_repo.get_job(session, job.id)
    assert stored is not None
    assert stored.locked_by == "worker-1"
    assert stored.attempt_count == 1


@pytest.mark.asyncio
async def test_watchdog_recovers_retryable_expired_running_job(session):
    database._async_session_factory = sessionmaker(
        session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    now = datetime.now(UTC)
    job = await job_repo.create_job(
        session,
        BackgroundJob(
            type="unknown",
            status="running",
            payload_json="{}",
            attempt_count=1,
            max_attempts=2,
            locked_by="worker-1",
            locked_at=now - timedelta(minutes=10),
            heartbeat_at=now - timedelta(minutes=10),
            lease_expires_at=now - timedelta(minutes=5),
        ),
    )
    await session.commit()

    watchdog = BackgroundWatchdog(transport=None, interval_seconds=1)
    recovered_count = await watchdog.run_once()

    await session.refresh(job)
    stored = await job_repo.get_job(session, job.id)
    assert recovered_count == 1
    assert stored is not None
    assert stored.status == JOB_STATUS_PENDING
    assert stored.locked_by is None


@pytest.mark.asyncio
async def test_watchdog_times_out_exhausted_expired_running_job(session):
    database._async_session_factory = sessionmaker(
        session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    now = datetime.now(UTC)
    job = await job_repo.create_job(
        session,
        BackgroundJob(
            type="unknown",
            status="running",
            payload_json="{}",
            attempt_count=1,
            max_attempts=1,
            locked_by="worker-1",
            locked_at=now - timedelta(minutes=10),
            heartbeat_at=now - timedelta(minutes=10),
            lease_expires_at=now - timedelta(minutes=5),
        ),
    )
    await session.commit()

    watchdog = BackgroundWatchdog(transport=None, interval_seconds=1)
    recovered_count = await watchdog.run_once()

    await session.refresh(job)
    stored = await job_repo.get_job(session, job.id)
    assert recovered_count == 1
    assert stored is not None
    assert stored.status == JOB_STATUS_TIMEOUT
