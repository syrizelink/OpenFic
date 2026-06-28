import json

import pytest
from sqlalchemy import select

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

    result = await session.execute(select(BackgroundJob).where(BackgroundJob.subject_id == task.id))
    job = result.scalar_one()
    payload = json.loads(job.payload_json)

    assert payload["seed_message"] == (
        '请基于<of-mention kind="chapter" chapter_id="chap_title_mentions" label="旧章节" />'
        '和<of-mention kind="line_range" chapter_id="chap_title_mentions" start_line="4" '
        'end_line="9" label="旧片段">保留快照</of-mention>命名'
    )
