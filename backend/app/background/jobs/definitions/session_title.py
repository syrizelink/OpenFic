"""Session title background job definition."""

import re
from datetime import UTC, datetime

from loguru import logger
from pydantic import BaseModel, Field

from app.background.events.types import EVENT_TASK_TITLE_UPDATED
from app.background.jobs import service as job_service
from app.background.jobs.base import JobDefinition
from app.background.jobs.constants import JOB_QUEUE_LLM, JOB_TYPE_SESSION_TITLE
from app.background.llm.resolver import BackgroundModelUnavailableError, resolve_background_llm
from app.background.runtime.context import JobContext
from app.agent_runtime.context.helpers.canonical_mentions import compile_canonical_mentions
from app.memory.prompt_chain_runner import ChatRuntime, build_chat_messages
from app.storage.repos import task_repo


class SessionTitleInput(BaseModel):
    task_id: str
    seed_message: str = Field(min_length=1)


class SessionTitleContext(BaseModel):
    project_id: str
    mode: str | None = None
    model_policy: str = "light_model"
    model_id: str | None = None


class SessionTitleResult(BaseModel):
    title: str
    task_id: str


async def handle_session_title(context: JobContext) -> dict[str, str] | None:
    await context.check_cancelled()
    payload = SessionTitleInput.model_validate(context.input)
    metadata = SessionTitleContext.model_validate(context.metadata)
    seed_message = payload.seed_message.strip()

    async def prepare_generation(session, job):
        try:
            resolved = await resolve_background_llm(
                session,
                model_policy=metadata.model_policy,
                model_id=metadata.model_id,
            )
        except BackgroundModelUnavailableError as exc:
            await job_service.mark_skipped(session, context.publisher, job, reason=str(exc))
            return None, None
        await job_service.update_progress(
            session,
            context.publisher,
            job,
            current=1,
            total=3,
            message="正在生成会话标题",
        )
        compiled_message = await compile_canonical_mentions(seed_message, session)
        messages = await build_chat_messages(
            session,
            mode_name="background",
            task_name="session_title",
            agent_name=None,
            runtime=ChatRuntime(current_message=compiled_message),
        )
        return resolved, messages

    resolved, messages = await context.with_short_session(prepare_generation)
    if resolved is None or messages is None:
        return None
    await context.check_cancelled()
    response = await resolved.client.generate(messages, timeout=60)
    await context.check_cancelled()
    title = _clean_title(response.content)
    if not title:
        logger.bind(job_id=context.job.id, task_id=payload.task_id).warning("生成标题为空，跳过更新")

        async def mark_empty_title_skipped(session, job):
            await job_service.mark_skipped(session, context.publisher, job, reason="生成标题为空")

        await context.with_short_session(mark_empty_title_skipped)
        return None

    async def save_title(session, job):
        await job_service.update_progress(
            session,
            context.publisher,
            job,
            current=2,
            total=3,
            message="正在保存会话标题",
        )
        task = await task_repo.get_by_id(session, payload.task_id)
        if task is None:
            await job_service.mark_skipped(
                session,
                context.publisher,
                job,
                reason=f"任务不存在: {payload.task_id}",
            )
            return None

        task.title = title
        task.updated_at = datetime.now(UTC)
        await task_repo.update_task(session, task)
        await job_service.append_event(
            session,
            context.publisher,
            job,
            event_type=EVENT_TASK_TITLE_UPDATED,
            payload={
                "task_id": task.id,
                "project_id": task.project_id,
                "agent_session_id": task.agent_session_id,
                "title": task.title,
                "updated_at": task.updated_at.isoformat(),
            },
        )
        await job_service.update_progress(
            session,
            context.publisher,
            job,
            current=3,
            total=3,
            message="会话标题已更新",
        )
        return task.id

    task_id = await context.with_short_session(save_title)
    if task_id is None:
        return None
    await context.check_cancelled()
    return {"title": title, "task_id": task_id}


def _clean_title(raw_title: str) -> str:
    title = raw_title.strip()
    title = re.sub(r"^[#\-\s]+", "", title)
    title = title.strip(" \t\n\r`*_\"'“”‘’《》")
    title = title.splitlines()[0].strip() if title else ""
    title = re.sub(r"[。.!！?？]+$", "", title).strip()
    if len(title) > 50:
        title = title[:50].rstrip()
    return title


SESSION_TITLE_JOB = JobDefinition(
    type=JOB_TYPE_SESSION_TITLE,
    name="Session title",
    description="Generate a concise title for a chat or agent session.",
    input_model=SessionTitleInput,
    result_model=SessionTitleResult,
    handler=handle_session_title,
    default_queue=JOB_QUEUE_LLM,
    default_timeout_seconds=90,
    default_max_attempts=1,
    supports_cancel=True,
)
