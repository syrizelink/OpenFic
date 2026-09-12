"""Background job for indexing project chapters into retrieval."""

import inspect
import json
from datetime import UTC, datetime
from typing import NoReturn

from loguru import logger
from pydantic import BaseModel

from app.background.jobs import repos as job_repo
from app.background.jobs import service as job_service
from app.background.jobs.base import JobDefinition
from app.background.jobs.constants import (
    JOB_QUEUE_DEFAULT,
    JOB_TYPE_RETRIEVAL_CHAPTER_INDEX_BATCH,
)
from app.background.jobs.models import BackgroundJobItem
from app.background.jobs.states import (
    JOB_STATUS_CANCELLED,
    JOB_STATUS_FAILED,
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
    JOB_STATUS_SUCCEEDED,
)
from app.background.runtime.context import JobCancelledError, JobContext
from app.core.encryption import EncryptionService
from app.models.clients.embedding_client import EmbeddingClient, EmbeddingConfig
from app.models.repos import model_provider_repo, model_repo
from app.models.services.model_provider_service import ModelProviderService
from app.retrieval.chapter_index import (
    ChapterIndexIntegrationService,
    build_keyword_only_model,
    chapter_document_id,
    chapter_index_key,
)
from app.retrieval.engine_protocol import is_keyword_only_model_ref
from app.retrieval.index_status import commit_and_emit_index_status
from app.retrieval.service import OpenFicRetrievalService
from app.settings import settings
from app.storage.repos import retrieval_chapter_index_state_repo, setting_repo


SETTING_KEY_DEFAULT_EMBEDDING_MODEL = "default_embedding_model"

# Jumlah maksimum potongan yang diproses per permintaan Embedding. Bab boleh melintasi
# beberapa permintaan, tetapi baru ditandai selesai setelah semua potongan berhasil ditulis;
# setiap permintaan melakukan commit dan mengirim progres tingkat bab.
MAX_EMBEDDING_CHUNKS_PER_REQUEST = 50


class RetrievalChapterIndexBatchInput(BaseModel):
    project_id: str


class RetrievalChapterIndexBatchContext(BaseModel):
    embedding_model_ref_id: str


async def _save_item(session, item: BackgroundJobItem) -> BackgroundJobItem:
    item.updated_at = datetime.now(UTC)
    return await job_repo.save_item(session, item)


async def _mark_item_running(session, item: BackgroundJobItem) -> BackgroundJobItem:
    item.status = JOB_STATUS_RUNNING
    item.started_at = item.started_at or datetime.now(UTC)
    item.finished_at = None
    return await _save_item(session, item)


async def _mark_item_terminal(
    session,
    item: BackgroundJobItem,
    status: str,
    *,
    error_message: str | None = None,
) -> BackgroundJobItem:
    item.status = status
    item.finished_at = datetime.now(UTC)
    item.error_json = (
        None
        if error_message is None
        else json.dumps({"message": error_message}, ensure_ascii=False)
    )
    return await _save_item(session, item)


async def _commit_and_emit(context: JobContext, project_id: str) -> None:
    await commit_and_emit_index_status(context.session, project_id)
    await job_service.publish_committed_events(context.session)
    await job_service.notify_submitted_jobs(context.session)


async def _finalize_and_abort(
    context: JobContext, *, project_id: str, reason: str
) -> NoReturn:
    """Menandai item yang belum selesai sebagai gagal, melakukan commit progres, lalu
    melempar eksepsi agar tugas ditandai gagal.

    Karena pengindeksan sebagian bab saja tidak diizinkan, kesalahan pada salah satu
    sub-batch harus menghentikan seluruh tugas, dan bab yang tersisa ditandai gagal
    secara seragam agar pengguna dapat memulai pengindeksan penuh kembali.

    Setelah eksepsi dilempar, worker menandai tugas sebagai failed dan menerbitkan
    event ``background_job_failed`` (membawa reason) sehingga frontend menampilkan
    toast error. Batch yang sudah berhasil di-commit sebelumnya tidak terpengaruh
    oleh rollback berikutnya.
    """
    await _finalize_incomplete_items(context, reason)
    await _commit_and_emit(context, project_id)
    raise RuntimeError(reason)


async def _build_embedding_client(session, model_ref_id: str):
    model = await model_repo.get_by_id(session, model_ref_id)
    if model is None or model.task_type != "embedding":
        raise ValueError(
            "default_embedding_model tidak ditemukan atau bukan model embedding"
        )
    provider = await model_provider_repo.get_by_id(session, model.provider_id)
    if provider is None:
        raise ValueError(
            "provider yang terkait dengan default_embedding_model tidak ditemukan"
        )
    provider_service = ModelProviderService(EncryptionService(settings.encryption_key))
    api_key = provider_service.get_decrypted_api_key(provider) or ""
    custom_headers = provider_service.get_decrypted_custom_headers(provider)
    return EmbeddingClient(
        EmbeddingConfig(
            provider_type=provider.provider_type,
            base_url=provider.url,
            api_key=api_key,
            model_id=model.model_id,
            custom_headers=custom_headers or None,
            dimensions=model.dimensions,
        )
    )


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


async def _finalize_incomplete_items(context: JobContext, reason: str) -> None:
    await _cleanup_incomplete_items(context, reason=reason, cancelled=False)


async def _handle_failed(context: JobContext, reason: str) -> None:
    await _finalize_incomplete_items(context, reason)


async def _handle_cancelled(context: JobContext, reason: str) -> None:
    """Membersihkan bab yang belum selesai agar pengindeksan berikutnya hanya
    memproses bab tersebut."""
    await _cleanup_incomplete_items(context, reason=reason, cancelled=True)
    project_id = RetrievalChapterIndexBatchInput.model_validate(context.input).project_id
    await _commit_and_emit(context, project_id)


async def _cleanup_incomplete_items(
    context: JobContext,
    *,
    reason: str,
    cancelled: bool,
) -> None:
    running_items = await job_repo.list_items_by_status(
        context.session,
        job_id=context.job_id,
        statuses={JOB_STATUS_RUNNING},
    )
    document_ids_by_index_key: dict[str, list[str]] = {}
    for item in running_items:
        payload = job_service.parse_json_object(item.payload_json)
        project_id = payload.get("project_id")
        chapter_id = payload.get("chapter_id")
        if isinstance(project_id, str) and isinstance(chapter_id, str):
            index_key = chapter_index_key(project_id)
            document_ids_by_index_key.setdefault(index_key, []).append(
                chapter_document_id(chapter_id)
            )

    retrieval_service = OpenFicRetrievalService()
    for index_key, document_ids in document_ids_by_index_key.items():
        try:
            await retrieval_service.delete_documents(
                context.session,
                index_key,
                document_ids,
            )
        except Exception as exc:
            logger.bind(
                job_id=context.job_id,
                index_key=index_key,
            ).warning(f"retrieval index document cleanup failed: {exc}")

    active_item_statuses = {JOB_STATUS_PENDING, JOB_STATUS_RUNNING}
    if cancelled:
        await retrieval_chapter_index_state_repo.reset_active_states_for_job(
            context.session,
            job_id=context.job_id,
        )
        await job_repo.mark_items_terminal_by_status(
            context.session,
            job_id=context.job_id,
            statuses=active_item_statuses,
            terminal_status=JOB_STATUS_CANCELLED,
        )
        return

    await retrieval_chapter_index_state_repo.fail_active_states_for_job(
        context.session,
        job_id=context.job_id,
        error_message=reason,
    )
    await job_repo.mark_items_terminal_by_status(
        context.session,
        job_id=context.job_id,
        statuses=active_item_statuses,
        terminal_status=JOB_STATUS_FAILED,
        error_json=json.dumps({"message": reason}, ensure_ascii=False),
    )


async def handle_retrieval_chapter_index_batch(context: JobContext) -> dict[str, int]:
    batch_input = RetrievalChapterIndexBatchInput.model_validate(context.input)
    metadata = RetrievalChapterIndexBatchContext.model_validate(context.metadata)
    project_id = batch_input.project_id

    # Mode keyword-only tidak bergantung pada pengaturan
    # ``default_embedding_model``, jadi tidak ada perubahan model yang perlu
    # dideteksi di sini.
    if not is_keyword_only_model_ref(metadata.embedding_model_ref_id):
        setting = await setting_repo.get_by_key(
            context.session,
            SETTING_KEY_DEFAULT_EMBEDDING_MODEL,
        )
        current_model_ref_id = setting.value.strip() if setting is not None else ""
        if current_model_ref_id != metadata.embedding_model_ref_id:
            await _finalize_and_abort(
                context,
                project_id=project_id,
                reason="default_embedding_model changed; retrieval index needs rebuild",
            )

    await context.check_cancelled()
    items = await job_service.list_job_items(context.session, job_id=context.job_id)
    pending_items = [
        item for item in items if item.status == JOB_STATUS_PENDING
    ]
    if not pending_items:
        return {
            "total": len(items),
            "succeeded": sum(
                1 for item in items if item.status == JOB_STATUS_SUCCEEDED
            ),
            "failed": sum(
                1 for item in items if item.status == JOB_STATUS_FAILED
            ),
        }

    chapter_ids: list[str] = []
    item_map: dict[str, BackgroundJobItem] = {}
    for item in pending_items:
        payload = job_service.parse_json_object(item.payload_json)
        cid = payload.get("chapter_id")
        if not isinstance(cid, str):
            await _mark_item_terminal(
                context.session,
                item,
                JOB_STATUS_FAILED,
                error_message="retrieval chapter item tidak memiliki chapter_id",
            )
            continue
        chapter_ids.append(cid)
        item_map[cid] = item

    if not chapter_ids:
        await _commit_and_emit(context, project_id)
        items = await job_service.list_job_items(context.session, job_id=context.job_id)
        return {
            "total": len(items),
            "succeeded": sum(
                1 for item in items if item.status == JOB_STATUS_SUCCEEDED
            ),
            "failed": sum(
                1 for item in items if item.status == JOB_STATUS_FAILED
            ),
        }

    # Dipecah menjadi sub-batch sesuai INDEX_BATCH_CHUNK_SIZE, tiap batch melakukan
    # commit transaksi sendiri dan mengirim progres.
    # Dengan begitu frontend melihat pembaruan bertahap (misalnya 10/101 -> 20/101
    # -> ...), bukan hanya melompat ke 100% saat semuanya selesai.
    #
    # Karena pengindeksan ulang sebagian bab saja tidak diizinkan, kesalahan pada
    # salah satu sub-batch (eksepsi atau kegagalan satu bab)
    # akan menghentikan seluruh tugas: setelah batch saat ini ditandai gagal, bab yang belum
    # diproses ditandai gagal secara seragam,
    # agar pengguna dapat memulai pengindeksan penuh kembali setelah menemukan masalahnya.
    try:
        # Mode keyword-only (SQLite FTS5): tidak ada model embedding nyata di
        # basis data dan tidak ada penyedia yang perlu dihubungi.
        if is_keyword_only_model_ref(metadata.embedding_model_ref_id):
            model = build_keyword_only_model()
            embedding_client = None
        else:
            resolved = await model_repo.get_by_id(
                context.session, metadata.embedding_model_ref_id
            )
            if resolved is None or resolved.task_type != "embedding":
                raise ValueError(
                    "default_embedding_model tidak ditemukan atau bukan model embedding"
                )
            model = resolved
            embedding_client = await _maybe_await(
                _build_embedding_client(
                    context.session, metadata.embedding_model_ref_id
                )
            )
        service = ChapterIndexIntegrationService()

        async def mark_chapter_running(chapter_id: str) -> None:
            item = item_map.get(chapter_id)
            if item is not None and item.status == JOB_STATUS_PENDING:
                await _mark_item_running(context.session, item)

        async for progress in service.stream_index_chapters(
            context.session,
            chapter_ids=chapter_ids,
            embedding_client=embedding_client,
            embedding_model=model,
            job_id=context.job_id,
            max_chunks_per_batch=MAX_EMBEDDING_CHUNKS_PER_REQUEST,
            check_cancelled=context.check_cancelled,
            on_chapter_started=mark_chapter_running,
        ):
            await context.check_cancelled()
            for chapter_id in progress.completed_chapter_ids:
                item = item_map.get(chapter_id)
                if item is not None:
                    await _mark_item_terminal(context.session, item, JOB_STATUS_SUCCEEDED)
            await _commit_and_emit(context, project_id)
    except JobCancelledError:
        raise
    except Exception as exc:
        await _finalize_and_abort(
            context, project_id=project_id, reason=f"Pengindeksan dihentikan: {exc}"
        )

    items = await job_service.list_job_items(context.session, job_id=context.job_id)
    return {
        "total": len(items),
        "succeeded": sum(
            1 for item in items if item.status == JOB_STATUS_SUCCEEDED
        ),
        "failed": sum(1 for item in items if item.status == JOB_STATUS_FAILED),
    }


RETRIEVAL_CHAPTER_INDEX_BATCH_JOB = JobDefinition(
    type=JOB_TYPE_RETRIEVAL_CHAPTER_INDEX_BATCH,
    name="Retrieval chapter index batch",
    description="Index project chapters into the retrieval vector store.",
    input_model=RetrievalChapterIndexBatchInput,
    handler=handle_retrieval_chapter_index_batch,
    on_failed=_handle_failed,
    on_timeout=_handle_failed,
    on_cancelled=_handle_cancelled,
    default_queue=JOB_QUEUE_DEFAULT,
    default_timeout_seconds=900,
    default_max_attempts=1,
    supports_cancel=True,
)
