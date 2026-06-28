"""Background job for indexing project chapters into retrieval."""

import inspect
import json
from datetime import UTC, datetime
from typing import NoReturn

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
    JOB_STATUS_FAILED,
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
    JOB_STATUS_SUCCEEDED,
)
from app.background.runtime.context import JobContext
from app.core.encryption import EncryptionService
from app.models.clients.embedding_client import EmbeddingClient, EmbeddingConfig
from app.models.repos import model_provider_repo, model_repo
from app.models.services.model_provider_service import ModelProviderService
from app.retrieval.chapter_index import (
    CHAPTER_INDEX_STATUS_FAILED,
    ChapterIndexIntegrationService,
    chapter_document_id,
)
from app.retrieval.index_status import schedule_emit_index_status
from app.settings import settings
from app.storage.repos import retrieval_chapter_index_state_repo, setting_repo


SETTING_KEY_DEFAULT_EMBEDDING_MODEL = "default_embedding_model"

# 每个子批处理的章节数。每批独立提交事务并推送进度，
# 使前端能看到增量进度而非只在全部完成后一次性更新。
INDEX_BATCH_CHUNK_SIZE = 10


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
    schedule_emit_index_status(context.session, project_id)
    await job_service.commit_and_notify(context.session)


async def _finalize_and_abort(
    context: JobContext, *, project_id: str, reason: str
) -> NoReturn:
    """标记剩余未完成 item 为失败、提交进度，然后抛出异常使任务标记为失败。

    由于不允许对部分章节单独索引，任一子批次出错后应停止整个任务，
    剩余待处理章节统一标记为失败以便用户重新发起完整索引。

    抛出异常后 worker 会将任务标记为 failed 并发布 ``background_job_failed``
    事件（携带 reason），前端据此 toast 报错。此前已提交的成功批次
    不受后续 rollback 影响。
    """
    await _finalize_incomplete_items(context, reason)
    await _commit_and_emit(context, project_id)
    raise RuntimeError(reason)


async def _build_embedding_client(session, model_ref_id: str):
    model = await model_repo.get_by_id(session, model_ref_id)
    if model is None or model.task_type != "embedding":
        raise ValueError("default_embedding_model 不存在或不是 embedding 模型")
    provider = await model_provider_repo.get_by_id(session, model.provider_id)
    if provider is None:
        raise ValueError("default_embedding_model 关联的 provider 不存在")
    provider_service = ModelProviderService(EncryptionService(settings.encryption_key))
    api_key = provider_service.get_decrypted_api_key(provider) or ""
    return EmbeddingClient(
        EmbeddingConfig(
            provider_type=provider.provider_type,
            base_url=provider.url,
            api_key=api_key,
            model_id=model.model_id,
            dimensions=model.dimensions,
        )
    )


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


async def _finalize_incomplete_items(context: JobContext, reason: str) -> None:
    items = await job_service.list_job_items(context.session, job_id=context.job_id)
    for item in items:
        if item.status not in {JOB_STATUS_PENDING, JOB_STATUS_RUNNING}:
            continue
        await _mark_state_failed(
            context,
            item,
            reason,
            expected_job_id=context.job_id,
            expected_item_id=item.id,
        )
        await _mark_item_terminal(
            context.session,
            item,
            JOB_STATUS_FAILED,
            error_message=reason,
        )


async def _handle_failed(context: JobContext, reason: str) -> None:
    await _finalize_incomplete_items(context, reason)


async def handle_retrieval_chapter_index_batch(context: JobContext) -> dict[str, int]:
    batch_input = RetrievalChapterIndexBatchInput.model_validate(context.input)
    metadata = RetrievalChapterIndexBatchContext.model_validate(context.metadata)
    project_id = batch_input.project_id

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

    for item in pending_items:
        await _mark_item_running(context.session, item)

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
                error_message="retrieval chapter item 缺少 chapter_id",
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

    model = await model_repo.get_by_id(
        context.session, metadata.embedding_model_ref_id
    )
    if model is None or model.task_type != "embedding":
        raise ValueError("default_embedding_model 不存在或不是 embedding 模型")

    embedding_client = await _maybe_await(
        _build_embedding_client(context.session, metadata.embedding_model_ref_id)
    )
    service = ChapterIndexIntegrationService()

    # 按 INDEX_BATCH_CHUNK_SIZE 拆分为子批次，每批独立提交事务并推送进度。
    # 这样前端能看到增量更新（如 10/101 → 20/101 → …），而非只在全完成时跳到 100%。
    #
    # 由于不允许对部分章节单独重新索引，任一子批次发生错误（异常或单章失败）
    # 都会终止整个任务：当前批次标记失败后，剩余未处理章节统一标记失败，
    # 以便用户发现问题后重新发起完整索引。
    for batch_start in range(0, len(chapter_ids), INDEX_BATCH_CHUNK_SIZE):
        await context.check_cancelled()
        batch_cids = chapter_ids[batch_start : batch_start + INDEX_BATCH_CHUNK_SIZE]
        batch_items = [item_map[cid] for cid in batch_cids if cid in item_map]

        try:
            result = await service.index_chapters(
                context.session,
                chapter_ids=batch_cids,
                embedding_client=embedding_client,
                embedding_model=model,
                job_id=context.job_id,
            )
        except Exception as exc:
            # 子批次异常：标记当前批次失败，终止整个任务。
            for item in batch_items:
                await _mark_item_terminal(
                    context.session,
                    item,
                    JOB_STATUS_FAILED,
                    error_message=str(exc),
                )
            await _finalize_and_abort(
                context, project_id=project_id, reason=f"索引中止：{exc}"
            )

        succeeded_doc_ids = {s.document_id for s in result.succeeded}
        failed_doc_ids = {f.document_id for f in result.failed}

        batch_has_failure = False
        for cid in batch_cids:
            batch_item: BackgroundJobItem | None = item_map.get(cid)
            if batch_item is None:
                continue
            doc_id = chapter_document_id(cid)
            if doc_id in succeeded_doc_ids:
                await _mark_item_terminal(context.session, batch_item, JOB_STATUS_SUCCEEDED)
            elif doc_id in failed_doc_ids:
                failure = next(
                    f for f in result.failed if f.document_id == doc_id
                )
                await _mark_item_terminal(
                    context.session,
                    batch_item,
                    JOB_STATUS_FAILED,
                    error_message=failure.error,
                )
                batch_has_failure = True
            else:
                await _mark_item_terminal(
                    context.session,
                    batch_item,
                    JOB_STATUS_FAILED,
                    error_message="chapter not in batch result",
                )
                batch_has_failure = True

        # 提交并推送当前批次进度。
        await _commit_and_emit(context, project_id)

        # 单章失败：终止整个任务，剩余章节统一标记失败。
        if batch_has_failure:
            await _finalize_and_abort(
                context, project_id=project_id, reason="索引中止：存在索引失败的章节"
            )

    items = await job_service.list_job_items(context.session, job_id=context.job_id)
    return {
        "total": len(items),
        "succeeded": sum(
            1 for item in items if item.status == JOB_STATUS_SUCCEEDED
        ),
        "failed": sum(1 for item in items if item.status == JOB_STATUS_FAILED),
    }


async def _mark_state_failed(
    context: JobContext,
    item: BackgroundJobItem,
    reason: str,
    *,
    expected_embedding_model_ref_id: str | None = None,
    expected_job_id: str | None = None,
    expected_item_id: str | None = None,
) -> None:
    payload = job_service.parse_json_object(item.payload_json)
    project_id = payload.get("project_id")
    chapter_id = payload.get("chapter_id")
    if not isinstance(project_id, str) or not isinstance(chapter_id, str):
        return
    state = await retrieval_chapter_index_state_repo.get_by_project_and_chapter(
        context.session,
        project_id=project_id,
        chapter_id=chapter_id,
        index_key=f"chapters:{project_id}",
    )
    if state is None:
        return
    if state.status == "needs_rebuild":
        state.error_message = None
        await retrieval_chapter_index_state_repo.save(context.session, state)
        return
    if (
        expected_job_id is not None
        and expected_item_id is not None
        and (state.job_id != expected_job_id or state.item_id != expected_item_id)
    ):
        return
    if expected_embedding_model_ref_id is not None:
        setting = await setting_repo.get_by_key(
            context.session,
            SETTING_KEY_DEFAULT_EMBEDDING_MODEL,
        )
        current_model_ref_id = setting.value.strip() if setting is not None else ""
        if current_model_ref_id != expected_embedding_model_ref_id:
            state.status = "needs_rebuild"
            state.job_id = None
            state.item_id = None
            state.error_message = None
            await retrieval_chapter_index_state_repo.save(context.session, state)
            return
    state.status = CHAPTER_INDEX_STATUS_FAILED
    state.error_message = reason
    await retrieval_chapter_index_state_repo.save(context.session, state)


RETRIEVAL_CHAPTER_INDEX_BATCH_JOB = JobDefinition(
    type=JOB_TYPE_RETRIEVAL_CHAPTER_INDEX_BATCH,
    name="Retrieval chapter index batch",
    description="Index project chapters into the retrieval vector store.",
    input_model=RetrievalChapterIndexBatchInput,
    handler=handle_retrieval_chapter_index_batch,
    on_failed=_handle_failed,
    on_timeout=_handle_failed,
    on_cancelled=_handle_failed,
    default_queue=JOB_QUEUE_DEFAULT,
    default_timeout_seconds=900,
    default_max_attempts=1,
    supports_cancel=True,
)
