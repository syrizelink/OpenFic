"""Session title background job definition."""

import re
from datetime import UTC, datetime

from loguru import logger
from pydantic import BaseModel, Field

from app.audit import AuditContext
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
            message="Sedang membuat judul sesi",
        )
        compiled_message = await compile_canonical_mentions(seed_message, session)
        messages = await build_chat_messages(
            session,
            prompt_id="session-title",
            runtime=ChatRuntime(current_message=compiled_message),
        )
        return resolved, messages

    resolved, messages = await context.with_short_session(prepare_generation)
    if resolved is None or messages is None:
        return None
    model_id = resolved.model.model_id
    model_provider = resolved.provider.provider_type
    model_name = resolved.model.name
    await context.check_cancelled()

    async def load_task_audit_context(session, _job):
        task = await task_repo.get_by_id(session, payload.task_id)
        if task is None:
            return None
        return AuditContext(
            project_id=metadata.project_id,
            category="session",
            task_id=task.id,
            session_id=task.agent_session_id,
            metadata={
                "background_job_id": context.job_id,
                "seed_message": seed_message,
            },
        )

    audit_context = await context.with_short_session(load_task_audit_context)
    if audit_context is None:
        return None
    async with audit_context.llm_call(
        operation="session_title",
        model_id=model_id,
        model_provider=model_provider,
        model_name=model_name,
        request_messages=messages,
    ) as audit:
        response = await resolved.client.generate(messages, timeout=60)
        audit.record_response(content=response.content, usage=response.usage)
    await context.check_cancelled()
    if _looks_like_provider_notice(response.content):
        logger.bind(
            job_id=context.job.id,
            task_id=payload.task_id,
            model_id=model_id,
            response_preview=response.content.strip()[:200],
        ).warning("Respons penyedia tampak berupa pemberitahuan galat, judul tidak diperbarui")

        async def mark_provider_notice_skipped(session, job):
            await job_service.mark_skipped(
                session,
                context.publisher,
                job,
                reason="Respons penyedia berupa pemberitahuan galat, bukan judul",
            )

        await context.with_short_session(mark_provider_notice_skipped)
        return None

    title = _clean_title(response.content)
    if not title:
        logger.bind(job_id=context.job.id, task_id=payload.task_id).warning(
            "Judul yang dibuat kosong, pembaruan dilewati"
        )

        async def mark_empty_title_skipped(session, job):
            await job_service.mark_skipped(
                session,
                context.publisher,
                job,
                reason="Judul yang dibuat kosong",
            )

        await context.with_short_session(mark_empty_title_skipped)
        return None

    async def save_title(session, job):
        await job_service.update_progress(
            session,
            context.publisher,
            job,
            current=2,
            total=3,
            message="Sedang menyimpan judul sesi",
        )
        task = await task_repo.get_by_id(session, payload.task_id)
        if task is None:
            await job_service.mark_skipped(
                session,
                context.publisher,
                job,
                reason=f"Tugas tidak ditemukan: {payload.task_id}",
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
            message="Judul sesi sudah diperbarui",
        )
        return task.id

    task_id = await context.with_short_session(save_title)
    if task_id is None:
        return None
    await context.check_cancelled()
    return {"title": title, "task_id": task_id}


_PROVIDER_NOTICE_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Ketersediaan/masa pakai model: "... is no longer available", "... has been deprecated".
    re.compile(
        r"\b(?:no longer|not|isn't|is not|are not)\s+(?:available|supported|accessible)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:deprecated|retired|sunset|discontinued|end[- ]of[- ]life)\b", re.IGNORECASE),
    re.compile(r"\bmodel\s+(?:not\s+found|unavailable|does\s+not\s+exist)\b", re.IGNORECASE),
    # Kuota, tagihan, dan pembatasan laju. Kata "quota"/"billing" sengaja menuntut
    # konteks agar judul wajar yang memuat kata itu tidak ikut tertolak.
    re.compile(r"\brate\s?limit(?:ed|ing)?\b", re.IGNORECASE),
    re.compile(
        r"\bquota\s+(?:exceeded|exhausted|reached)\b"
        r"|\bexceed(?:ed)?\s+(?:your\s+)?(?:current\s+)?quota\b"
        r"|\binsufficient\s+(?:quota|credits?|balance|funds)\b"
        r"|\bbilling\s+(?:error|issue|problem|required|details)\b",
        re.IGNORECASE,
    ),
    # Autentikasi dan otorisasi.
    re.compile(r"\b(?:api\s?key|unauthorized|forbidden|permission\s+denied)\b", re.IGNORECASE),
    # Kegagalan sisi layanan.
    re.compile(
        r"\b(?:internal\s+server\s+error|service\s+unavailable|overloaded|try\s+again\s+later|"
        r"upstream\s+error|bad\s+gateway)\b",
        re.IGNORECASE,
    ),
    # Bentuk galat terstruktur yang kadang lolos sebagai konten biasa.
    re.compile(r"^\s*[\[{]?\s*\"?error\"?\s*[\]}:]", re.IGNORECASE),
    re.compile(r"\bhttp\s*(?:status\s*)?[45]\d{2}\b", re.IGNORECASE),
)


def _looks_like_provider_notice(raw_title: str) -> bool:
    """Deteksi respons penyedia yang berupa pemberitahuan galat, bukan judul.

    Penyedia di balik gerbang API kadang menjawab HTTP 200 dengan teks pemberitahuan
    (misalnya model sudah tidak tersedia) sebagai konten completion biasa. Tanpa
    pemeriksaan ini teks tersebut tersimpan menjadi judul sesi secara permanen,
    karena judul hanya dibuat sekali per sesi.

    Pemeriksaan dilakukan pada teks mentah sebelum pemotongan 50 karakter, supaya
    frasa penanda di bagian akhir pesan tidak ikut terpotong.
    """
    text = raw_title.strip()
    if not text:
        return False
    return any(pattern.search(text) for pattern in _PROVIDER_NOTICE_PATTERNS)


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
