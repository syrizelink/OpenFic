"""Session title background job scheduling."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.background.jobs import service as background_service
from app.background.jobs.constants import JOB_TYPE_SESSION_TITLE
from app.storage.models.task import Task


async def enqueue_session_title_job(
    session: AsyncSession,
    task: Task,
    seed_message: str,
) -> None:
    seed = seed_message.strip()
    if not seed:
        return
    await background_service.submit_job(
        session,
        job_type=JOB_TYPE_SESSION_TITLE,
        payload={
            "task_id": task.id,
            "seed_message": seed,
        },
        context={
            "project_id": task.project_id,
            "model_policy": "light_model",
        },
        subject_type="task",
        subject_id=task.id,
    )
