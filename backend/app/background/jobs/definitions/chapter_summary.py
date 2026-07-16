"""Summary background job definitions."""

from pydantic import BaseModel

from app.audit import AuditContext
from app.background.events.types import EVENT_CHAPTER_SUMMARY_UPDATED, EVENT_LONG_TERM_SUMMARY_UPDATED
from app.background.jobs import service as job_service
from app.background.jobs.base import JobDefinition
from app.background.jobs.constants import JOB_QUEUE_LLM, JOB_TYPE_CHAPTER_SUMMARY, JOB_TYPE_LONG_TERM_SUMMARY
from app.background.jobs.definitions.summary_batch import (
    ERROR_MSG_INSUFFICIENT_SOURCE,
    PROGRESS_MSG_CHAPTER_COMPLETED,
    PROGRESS_MSG_CHAPTER_GENERATING,
    PROGRESS_MSG_CHAPTER_SAVED,
    PROGRESS_MSG_LONG_TERM_COMPLETED,
    PROGRESS_MSG_LONG_TERM_GENERATING,
    PROGRESS_MSG_LONG_TERM_SAVED,
)
from app.background.llm.resolver import BackgroundModelUnavailableError, resolve_background_llm
from app.background.runtime.context import JobContext
from app.memory.chapter import summary_generator, summary_service
from app.storage.repos import chapter_repo, chapter_summary_repo


class SummaryJobContext(BaseModel):
    project_id: str
    model_policy: str = "light_model"
    model_id: str | None = None


class ChapterSummaryInput(BaseModel):
    chapter_id: str


class ChapterSummaryResult(BaseModel):
    summary_id: str
    chapter_id: str


class LongTermSummaryInput(BaseModel):
    project_id: str
    start_order: int
    end_order: int


class LongTermSummaryResult(BaseModel):
    summary_id: str
    project_id: str


async def handle_chapter_summary(context: JobContext) -> dict[str, str] | None:
    await context.check_cancelled()
    payload = ChapterSummaryInput.model_validate(context.input)
    metadata = SummaryJobContext.model_validate(context.metadata)

    async def prepare_generation(session, job):
        try:
            resolved = await resolve_background_llm(
                session,
                model_policy=metadata.model_policy,
                model_id=metadata.model_id,
            )
        except BackgroundModelUnavailableError as exc:
            await _mark_chapter_failed(context, payload.chapter_id, str(exc), session=session, job=job)
            await job_service.mark_skipped(session, context.publisher, job, reason=str(exc))
            return None, None, None
        row = await summary_service.mark_chapter_summary_running(
            session, payload.chapter_id, job.id, resolved.model.id
        )
        await _publish_chapter_update(context, row, session=session, job=job)
        await job_service.update_progress(
            session,
            context.publisher,
            job,
            current=1,
            total=3,
            message=PROGRESS_MSG_CHAPTER_GENERATING,
        )
        prompt = await summary_generator.build_chapter_summary_prompt(session, payload.chapter_id)
        return resolved, prompt, row

    resolved, prompt, summary_row = await context.with_short_session(prepare_generation)
    if resolved is None or prompt is None or summary_row is None:
        return None
    model_id = resolved.model.id
    await context.check_cancelled()

    result = await summary_generator.generate_chapter_summary_from_prompt(
        resolved.client,
        prompt,
        audit_context=AuditContext(
            project_id=metadata.project_id,
            category="memory",
            chapter_id=payload.chapter_id,
            metadata={
                "background_job_id": context.job_id,
                "summary_id": summary_row.id,
                "summary_type": "chapter",
            },
        ),
        model_id=getattr(resolved.model, "model_id", resolved.model.id),
        model_provider=getattr(getattr(resolved, "provider", None), "provider_type", None),
        model_name=getattr(resolved.model, "name", None),
    )
    await context.check_cancelled()

    async def save_result(session, job):
        row = await summary_service.save_chapter_summary_result(
            session,
            payload.chapter_id,
            start_time=result.start_time,
            end_time=result.end_time,
            characters=result.characters,
            locations=result.locations,
            summary=result.summary,
            token_count=result.token_count,
            model_id=model_id,
            job_id=job.id,
        )
        await job_service.update_progress(
            session,
            context.publisher,
            job,
            current=2,
            total=3,
            message=PROGRESS_MSG_CHAPTER_SAVED,
        )
        await _publish_chapter_update(context, row, session=session, job=job)
        await summary_service.enqueue_long_term_summary_if_ready(
            session,
            row.project_id,
            model_id=model_id,
            model_policy=metadata.model_policy,
        )
        await job_service.update_progress(
            session,
            context.publisher,
            job,
            current=3,
            total=3,
            message=PROGRESS_MSG_CHAPTER_COMPLETED,
        )
        return row.id

    summary_id = await context.with_short_session(save_result)
    await context.check_cancelled()
    return {"summary_id": summary_id, "chapter_id": payload.chapter_id}


async def handle_long_term_summary(context: JobContext) -> dict[str, str] | None:
    await context.check_cancelled()
    payload = LongTermSummaryInput.model_validate(context.input)
    metadata = SummaryJobContext.model_validate(context.metadata)

    async def prepare_generation(session, job):
        window = await summary_service.load_long_term_summary_window(
            session, payload.project_id, payload.start_order, payload.end_order
        )
        if window is None:
            await job_service.mark_skipped(session, context.publisher, job, reason=ERROR_MSG_INSUFFICIENT_SOURCE)
            return None, None, None, None
        source = window.source_summaries
        chapters = await chapter_repo.list_by_project(session, payload.project_id)
        try:
            resolved = await resolve_background_llm(
                session,
                model_policy=metadata.model_policy,
                model_id=metadata.model_id,
            )
        except BackgroundModelUnavailableError as exc:
            row = await summary_service.create_or_update_long_term_summary(
                session,
                payload.project_id,
                source,
                start_order=payload.start_order,
                end_order=payload.end_order,
                status=chapter_summary_repo.SUMMARY_STATUS_FAILED,
                source_chapter_ids=await summary_service.load_long_term_chapter_ids(
                    session, payload.project_id, payload.start_order, payload.end_order
                ),
                job_id=job.id,
            )
            await summary_service.mark_summary_failed(session, row, str(exc))
            await job_service.mark_skipped(session, context.publisher, job, reason=str(exc))
            return None, None, None, None

        row = await summary_service.create_or_update_long_term_summary(
            session,
            payload.project_id,
            source,
            start_order=payload.start_order,
            end_order=payload.end_order,
            status=chapter_summary_repo.SUMMARY_STATUS_RUNNING,
            source_chapter_ids=await summary_service.load_long_term_chapter_ids(
                session, payload.project_id, payload.start_order, payload.end_order
            ),
            job_id=job.id,
            model_id=resolved.model.id,
        )
        await _publish_long_term_update(context, row, session=session, job=job)
        await job_service.update_progress(
            session,
            context.publisher,
            job,
            current=1,
            total=3,
            message=PROGRESS_MSG_LONG_TERM_GENERATING,
        )
        prompt = await summary_generator.build_long_term_summary_prompt(session, source, chapters)
        return resolved, source, prompt, row

    resolved, source, prompt, summary_row = await context.with_short_session(prepare_generation)
    if resolved is None or source is None or prompt is None or summary_row is None:
        return None
    model_id = resolved.model.id
    await context.check_cancelled()

    result = await summary_generator.generate_long_term_summary_from_prompt(
        resolved.client,
        prompt,
        audit_context=AuditContext(
            project_id=payload.project_id,
            category="memory",
            metadata={
                "background_job_id": context.job_id,
                "summary_id": summary_row.id,
                "summary_type": "long_term",
                "start_order": payload.start_order,
                "end_order": payload.end_order,
            },
        ),
        model_id=getattr(resolved.model, "model_id", resolved.model.id),
        model_provider=getattr(getattr(resolved, "provider", None), "provider_type", None),
        model_name=getattr(resolved.model, "name", None),
    )
    await context.check_cancelled()

    async def save_result(session, job):
        window = await summary_service.load_long_term_summary_window(
            session, payload.project_id, payload.start_order, payload.end_order
        )
        if window is None:
            raise ValueError(ERROR_MSG_INSUFFICIENT_SOURCE)
        source = window.source_summaries
        row = await summary_service.save_long_term_summary_result(
            session,
            payload.project_id,
            source,
            start_order=payload.start_order,
            end_order=payload.end_order,
            start_time=result.start_time,
            end_time=result.end_time,
            summary=result.summary,
            token_count=result.token_count,
            model_id=model_id,
            job_id=job.id,
            source_chapter_ids=await summary_service.load_long_term_chapter_ids(
                session, payload.project_id, payload.start_order, payload.end_order
            ),
        )
        await job_service.update_progress(
            session,
            context.publisher,
            job,
            current=2,
            total=3,
            message=PROGRESS_MSG_LONG_TERM_SAVED,
        )
        await _publish_long_term_update(context, row, session=session, job=job)
        await job_service.update_progress(
            session,
            context.publisher,
            job,
            current=3,
            total=3,
            message=PROGRESS_MSG_LONG_TERM_COMPLETED,
        )
        return row.id

    summary_id = await context.with_short_session(save_result)
    await context.check_cancelled()
    return {"summary_id": summary_id, "project_id": payload.project_id}


async def mark_chapter_summary_failed(context: JobContext, reason: str) -> None:
    payload = ChapterSummaryInput.model_validate(context.input)
    summary = await chapter_summary_repo.get_by_chapter_id(context.session, payload.chapter_id)
    if summary is None:
        return
    row = await summary_service.mark_summary_failed(context.session, summary, reason)
    await _publish_chapter_update(context, row)


async def mark_long_term_summary_failed(context: JobContext, reason: str) -> None:
    payload = LongTermSummaryInput.model_validate(context.input)
    row = await chapter_summary_repo.get_long_term_by_range(
        context.session,
        payload.project_id,
        payload.start_order,
        payload.end_order,
    )
    if row is None:
        return
    row = await summary_service.mark_summary_failed(context.session, row, reason)
    await _publish_long_term_update(context, row)


async def _mark_chapter_failed(
    context: JobContext,
    chapter_id: str,
    reason: str,
    *,
    session=None,
    job=None,
) -> None:
    session = session or context.session
    job = job or context.job
    summary = await chapter_summary_repo.get_by_chapter_id(session, chapter_id)
    if summary:
        await summary_service.mark_summary_failed(session, summary, reason)
        await _publish_chapter_update(context, summary, session=session, job=job)


async def _publish_chapter_update(context: JobContext, row, *, session=None, job=None) -> None:
    await job_service.append_event(
        session or context.session,
        context.publisher,
        job or context.job,
        event_type=EVENT_CHAPTER_SUMMARY_UPDATED,
        payload={
            "project_id": row.project_id,
            "chapter_id": row.chapter_id,
            "summary_id": row.id,
            "status": row.status,
            "updated_at": row.updated_at.isoformat(),
        },
        item_id=row.job_id,
        item_type="chapter_summary",
    )


async def _publish_long_term_update(context: JobContext, row, *, session=None, job=None) -> None:
    await job_service.append_event(
        session or context.session,
        context.publisher,
        job or context.job,
        event_type=EVENT_LONG_TERM_SUMMARY_UPDATED,
        payload={
            "project_id": row.project_id,
            "summary_id": row.id,
            "status": row.status,
            "start_order": row.start_order,
            "end_order": row.end_order,
            "updated_at": row.updated_at.isoformat(),
        },
        item_id=row.job_id,
        item_type="long_term_summary",
    )


CHAPTER_SUMMARY_JOB = JobDefinition(
    type=JOB_TYPE_CHAPTER_SUMMARY,
    name="Chapter summary",
    description="Generate structured memory for one chapter.",
    input_model=ChapterSummaryInput,
    result_model=ChapterSummaryResult,
    handler=handle_chapter_summary,
    on_failed=mark_chapter_summary_failed,
    on_timeout=mark_chapter_summary_failed,
    on_cancelled=mark_chapter_summary_failed,
    default_queue=JOB_QUEUE_LLM,
    default_timeout_seconds=180,
    default_max_attempts=1,
    supports_cancel=True,
)

LONG_TERM_SUMMARY_JOB = JobDefinition(
    type=JOB_TYPE_LONG_TERM_SUMMARY,
    name="Long-term summary",
    description="Aggregate ready chapter summaries into long-term memory.",
    input_model=LongTermSummaryInput,
    result_model=LongTermSummaryResult,
    handler=handle_long_term_summary,
    on_failed=mark_long_term_summary_failed,
    on_timeout=mark_long_term_summary_failed,
    on_cancelled=mark_long_term_summary_failed,
    default_queue=JOB_QUEUE_LLM,
    default_timeout_seconds=240,
    default_max_attempts=1,
    supports_cancel=True,
)
