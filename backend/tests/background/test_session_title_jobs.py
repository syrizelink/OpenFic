import json

import pytest
from sqlalchemy import select
from sqlmodel import col

from app.background.jobs.models import BackgroundJob
from app.background.jobs.session_title_jobs import enqueue_session_title_job
from app.storage.models.chapter import Chapter
from app.storage.models.project import Project
from app.storage.models.task import Task
from app.storage.models.volume import Volume

pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_enqueue_session_title_job_keeps_raw_seed_message(session):
    project = Project(id="proj_title_mentions", title="标题提及项目")
    volume = Volume(
        id="vol_title_mentions",
        project_id=project.id,
        title="现卷标题",
        order=1,
        chapter_count=1,
    )
    chapter = Chapter(
        id="chap_title_mentions",
        project_id=project.id,
        volume_id=volume.id,
        title="现章节标题",
        order=1,
    )
    task = Task(
        id="task_title_mentions",
        project_id=project.id,
        title="Agent Session",
        mode="agent",
    )
    session.add(project)
    session.add(volume)
    session.add(chapter)
    session.add(task)
    await session.commit()

    await enqueue_session_title_job(
        session,
        task,
        (
            '请基于<of-mention kind="chapter" chapter_id="chap_title_mentions" label="旧章节" />'
            '和<of-mention kind="line_range" chapter_id="chap_title_mentions" start_line="4" '
            'end_line="9" label="旧片段">保留快照</of-mention>命名'
        ),
    )
    await session.commit()

    result = await session.execute(
        select(BackgroundJob).where(col(BackgroundJob.subject_id) == task.id)
    )
    job = result.scalar_one()
    payload = json.loads(job.payload_json)

    assert payload["seed_message"] == (
        '请基于<of-mention kind="chapter" chapter_id="chap_title_mentions" label="旧章节" />'
        '和<of-mention kind="line_range" chapter_id="chap_title_mentions" start_line="4" '
        'end_line="9" label="旧片段">保留快照</of-mention>命名'
    )


async def test_enqueue_session_title_job_reuses_active_job_for_same_task(session):
    project = Project(id="proj_title_dedup", title="标题去重项目")
    task = Task(
        id="task_title_dedup",
        project_id=project.id,
        title="Agent Session",
        mode="agent",
    )
    session.add(project)
    session.add(task)
    await session.commit()

    await enqueue_session_title_job(session, task, "第一条消息")
    await enqueue_session_title_job(session, task, "第二条消息")
    await session.commit()

    result = await session.execute(
        select(BackgroundJob).where(col(BackgroundJob.subject_id) == task.id)
    )
    jobs = list(result.scalars())

    assert len(jobs) == 1
    assert json.loads(jobs[0].payload_json)["seed_message"] == "第一条消息"
