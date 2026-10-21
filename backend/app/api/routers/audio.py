"""ASR configuration, explicit model preparation and transcription endpoints."""

import asyncio
from time import monotonic
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.asr.audio import MAX_BYTES, validate_audio
from app.asr.config import (
    ASRUpdate,
    ProviderConfig,
    load_config,
    public_config,
    SETTING_KEY,
)
from app.asr.models import PreparationProgress, prepare, ready
from app.asr.service import transcribe
from app.core.encryption import EncryptionService
from app.settings import settings
from app.storage.database import get_session
from app.storage.repos import setting_repo

router = APIRouter(prefix="/audio", tags=["audio"])


@router.get("/config")
async def get_config(session: AsyncSession = Depends(get_session)):
    return public_config(await load_config(session))


@router.put("/config")
async def update_config(body: ASRUpdate, session: AsyncSession = Depends(get_session)):
    config = await load_config(session)
    selected = body.config.model_copy()
    # Ciphertext is never accepted from the client.
    selected.api_key_encrypted = config.providers.get(
        body.provider, ProviderConfig()
    ).api_key_encrypted
    if body.api_key is not None:
        selected.api_key_encrypted = (
            EncryptionService(settings.encryption_key).encrypt(body.api_key)
            if body.api_key
            else ""
        )
    config.enabled, config.provider, config.language = (
        body.enabled,
        body.provider,
        body.language,
    )
    config.providers[body.provider] = selected
    await setting_repo.upsert(session, SETTING_KEY, config.model_dump_json())
    await session.commit()
    return public_config(config)


@router.get("/local-status")
async def local_status(session: AsyncSession = Depends(get_session)):
    config = await load_config(session)
    return {
        "sensevoice_ready": await asyncio.to_thread(
            ready, config.providers.get("sensevoice", ProviderConfig())
        ),
    }


@router.get("/prepare/status", response_model=PreparationProgress)
async def preparation_status(request: Request):
    return getattr(request.app.state, "asr_preparation", PreparationProgress())


@router.post("/prepare")
async def prepare_model(request: Request, session: AsyncSession = Depends(get_session)):
    config = await load_config(session)
    if config.provider != "sensevoice":
        raise HTTPException(
            400,
            "Automatic preparation is available only for SenseVoice",
        )
    if getattr(request.app.state, "asr_preparing", False):
        raise HTTPException(409, "Model preparation is already running")
    request.app.state.asr_preparing = True
    request.app.state.asr_preparation = PreparationProgress(status="verifying")

    def report(progress: PreparationProgress):
        request.app.state.asr_preparation = progress

    try:
        async with asyncio.timeout(600):
            await prepare(config.providers.get("sensevoice", ProviderConfig()), report)
        return {"ready": True}
    except (TimeoutError, httpx.TimeoutException) as exc:
        raise HTTPException(
            504, "Model preparation timed out; retry to reuse verified files"
        ) from exc
    except (httpx.HTTPError, OSError) as exc:
        raise HTTPException(
            502, "Model preparation failed; check network and storage, then retry"
        ) from exc
    finally:
        request.app.state.asr_preparing = False
        progress = request.app.state.asr_preparation
        if progress.status != "ready":
            request.app.state.asr_preparation = progress.model_copy(
                update={"status": "failed"}
            )


@router.post("/transcriptions")
async def transcription(
    request: Request,
    file: UploadFile = File(...),
    request_id: UUID | None = Form(None),
    session: AsyncSession = Depends(get_session),
):
    config = await load_config(session)
    if not config.enabled:
        await file.close()
        raise HTTPException(409, "Enable speech recognition in settings first")
    try:
        audio = await file.read(MAX_BYTES + 1)
    finally:
        await file.close()
    if len(audio) > MAX_BYTES:
        raise HTTPException(413, "Audio exceeds the five-minute recording limit")
    duration = validate_audio(audio)
    text = await transcribe(
        request, config, audio, str(request_id) if request_id else ""
    )
    return {"text": text, "provider": config.provider, "audio_seconds": duration}


@router.delete("/transcriptions/{request_id}")
async def cancel_transcription(request_id: UUID, request: Request):
    # Explicit cancellation also works behind proxies that retain upstream sockets.
    identity = str(request_id)
    cancelled = getattr(request.app.state, "asr_cancelled", {})
    request.app.state.asr_cancelled = cancelled
    cancelled[identity] = monotonic()
    while len(cancelled) > 128:
        cancelled.pop(next(iter(cancelled)))
    job = getattr(request.app.state, "asr_jobs", {}).get(identity)
    if job:
        work, finished = job
        if not work.done() and not work.cancelling():
            work.cancel()
        await finished.wait()
    return {"cancelled": True}
