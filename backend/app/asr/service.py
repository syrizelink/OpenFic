"""Bounded ASR dispatch; audio stays in memory and keys never reach the browser."""

import asyncio
import json
import sys
from pathlib import Path
from time import monotonic

import httpx
from fastapi import HTTPException, Request

from app.asr.config import ASRConfig, DEFAULTS, ProviderConfig, decrypt_key

TRANSCRIPTION_TIMEOUT = 180


async def local_transcribe(config: ASRConfig, audio: bytes) -> str:
    selected = config.providers.get(config.provider, ProviderConfig())
    if config.language not in {
        "auto",
        "zh",
        "en",
        "ja",
        "ko",
        "yue",
    }:
        raise HTTPException(400, "SenseVoice supports auto, zh, en, ja, ko and yue")
    from app.asr.models import resolve_paths

    paths = await asyncio.to_thread(resolve_paths, selected)
    payload = {"language": config.language, **paths}
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(Path(__file__).with_name("worker.py")),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except OSError as exc:
        raise HTTPException(503, "Cannot start the local ASR worker") from exc
    try:
        output, _ = await process.communicate(
            json.dumps(payload).encode() + b"\n" + audio
        )
        if process.returncode:
            raise HTTPException(
                503,
                "Local ASR failed. Install the ASR extra and prepare the model; check model paths.",
            )
        try:
            result = json.loads(output)
            if not isinstance(result, dict) or not isinstance(result.get("text"), str):
                raise ValueError("Invalid worker response")
        except (ValueError, TypeError) as exc:
            raise HTTPException(
                503, "Local ASR worker returned an invalid response"
            ) from exc
        return result["text"].strip()
    finally:
        if process.returncode is None:
            process.kill()
        await process.wait()


async def cloud_transcribe(config: ASRConfig, audio: bytes) -> str:
    selected = config.providers.get(config.provider, ProviderConfig())
    key = decrypt_key(selected)
    # Custom OpenAI-compatible local servers may not require authentication.
    if not key and not (config.provider == "openai" and selected.base_url):
        raise HTTPException(400, "Configure an API key for this ASR provider")
    default_url, default_model = DEFAULTS[config.provider]
    base = selected.base_url or default_url
    model = selected.model or default_model
    language = config.language
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    async with httpx.AsyncClient(timeout=120, follow_redirects=False) as client:
        if config.provider == "deepgram":
            params = {"model": model, "smart_format": "true"}
            params.update(
                {"detect_language": "true"}
                if language == "auto"
                else {"language": language}
            )
            response = await client.post(
                f"{base}/listen",
                params=params,
                content=audio,
                headers={"Authorization": f"Token {key}", "Content-Type": "audio/wav"},
            )
        elif config.provider == "azure":
            definition = {} if language == "auto" else {"locales": [language]}
            response = await client.post(
                f"{base}/speechtotext/transcriptions:transcribe",
                params={"api-version": "2024-11-15"},
                headers={"Ocp-Apim-Subscription-Key": key},
                data={"definition": json.dumps(definition)},
                files={"audio": ("audio.wav", audio, "audio/wav")},
            )
        else:
            data = {"model": model, "response_format": "json"}
            if config.provider == "mistral":
                data.pop("response_format")
            if language != "auto":
                data["language"] = language
            response = await client.post(
                f"{base}/audio/transcriptions",
                headers=headers,
                data=data,
                files={"file": ("audio.wav", audio, "audio/wav")},
            )
        if response.is_error:
            # Upstream bodies can contain keys, URLs and transcripts.
            raise HTTPException(
                502, f"ASR provider returned HTTP {response.status_code}"
            )
        try:
            result = response.json()
            if config.provider == "deepgram":
                text = result["results"]["channels"][0]["alternatives"][0]["transcript"]
            elif config.provider == "azure":
                text = " ".join(item["text"] for item in result["combinedPhrases"])
            else:
                text = result["text"]
            if not isinstance(text, str):
                raise ValueError("Invalid text")
            return text.strip()
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise HTTPException(
                502, "ASR provider returned an invalid transcription"
            ) from exc


async def transcribe(
    request: Request, config: ASRConfig, audio: bytes, request_id: str = ""
) -> str:
    cancelled = getattr(request.app.state, "asr_cancelled", {})
    if request_id in cancelled and monotonic() - cancelled[request_id] < 60:
        raise HTTPException(499, "Transcription cancelled")
    # Reject excess work rather than queue unbounded audio buffers in memory.
    if getattr(request.app.state, "asr_busy", False):
        raise HTTPException(429, "Speech recognition is busy; try again shortly")
    request.app.state.asr_busy = True

    async def run():
        return await (
            local_transcribe(config, audio)
            if config.provider == "sensevoice"
            else cloud_transcribe(config, audio)
        )

    work = asyncio.create_task(run())
    finished = asyncio.Event()
    jobs = getattr(request.app.state, "asr_jobs", {})
    request.app.state.asr_jobs = jobs
    if request_id:
        jobs[request_id] = (work, finished)
    try:
        async with asyncio.timeout(TRANSCRIPTION_TIMEOUT):
            while not work.done():
                if await request.is_disconnected():
                    raise HTTPException(499, "Transcription cancelled")
                await asyncio.wait({work}, timeout=0.2)
            return await work
    except (TimeoutError, httpx.TimeoutException) as exc:
        raise HTTPException(504, "Speech recognition timed out") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Cannot connect to the ASR provider") from exc
    except asyncio.CancelledError as exc:
        raise HTTPException(499, "Transcription cancelled") from exc
    finally:
        if not work.done() and not work.cancelling():
            work.cancel()
        await asyncio.gather(work, return_exceptions=True)
        request.app.state.asr_busy = False
        jobs.pop(request_id, None)
        finished.set()
