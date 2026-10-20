"""ASR API contracts, provider protocols, isolation and failure handling."""

import asyncio
import io
import json
import wave
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
import respx
from fastapi import HTTPException, Request, FastAPI

from app.asr.audio import MAX_BYTES, validate_audio
from app.asr.config import SETTING_KEY, ASRConfig, load_config
from app.asr.service import local_transcribe, transcribe
from app.storage.repos import setting_repo


def wav(*, rate=16000, channels=1, width=2, seconds=0.1):
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(channels)
        target.setsampwidth(width)
        target.setframerate(rate)
        target.writeframes(b"\0" * int(rate * seconds) * channels * width)
    return output.getvalue()


async def configure(client, provider="openai", **kwargs):
    response = await client.put(
        "/api/v1/audio/config",
        json={
            "enabled": True,
            "provider": provider,
            "api_key": "test-secret",
            **kwargs,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_config_defaults_and_encryption(client, session):
    initial = (await client.get("/api/v1/audio/config")).json()
    assert initial["enabled"] is False
    assert len(initial["providers"]) == 6
    saved = await configure(client)
    assert saved["providers"]["openai"]["has_api_key"]
    row = await setting_repo.get_by_key(session, SETTING_KEY)
    assert "test-secret" not in row.value
    assert "api_key_encrypted" not in json.dumps(saved)
    await configure(client, "deepgram", api_key="second-secret")
    await configure(client, api_key=None)
    assert (await load_config(session)).providers["openai"].api_key_encrypted
    saved = await configure(client, api_key="")
    assert not saved["providers"]["openai"]["has_api_key"]
    assert saved["providers"]["deepgram"]["has_api_key"]


@pytest.mark.parametrize(
    "body",
    [
        {"provider": "unknown"},
        {"provider": "whisper"},
        {"language": "not a language"},
        {"config": {"base_url": "file:///etc/passwd"}},
        {"config": {"base_url": "https://key:secret@example.com"}},
        {"config": {"base_url": "https://example.com?key=secret"}},
    ],
)
async def test_invalid_configuration(client, body):
    response = await client.put(
        "/api/v1/audio/config", json={"enabled": True, "provider": "openai", **body}
    )
    assert response.status_code == 422


async def test_disabled_and_invalid_audio_never_dispatch(client, monkeypatch):
    dispatch = AsyncMock()
    monkeypatch.setattr("app.api.routers.audio.transcribe", dispatch)
    assert (
        await client.post(
            "/api/v1/audio/transcriptions", files={"file": ("test.wav", wav())}
        )
    ).status_code == 409
    await configure(client)
    for data in [
        b"",
        b"not audio",
        wav(rate=8000),
        wav(channels=2),
        wav(width=1),
        wav()[:-2],
    ]:
        response = await client.post(
            "/api/v1/audio/transcriptions", files={"file": ("test.wav", data)}
        )
        assert response.status_code == 400, response.text
    response = await client.post(
        "/api/v1/audio/transcriptions",
        files={"file": ("test.wav", b"x" * (MAX_BYTES + 1))},
    )
    assert response.status_code == 413
    dispatch.assert_not_awaited()


@pytest.mark.parametrize(
    "provider,endpoint,response",
    [
        (
            "openai",
            "https://api.openai.com/v1/audio/transcriptions",
            {"text": "  你好，世界。  "},
        ),
        (
            "groq",
            "https://api.groq.com/openai/v1/audio/transcriptions",
            {"text": "你好，世界。"},
        ),
        (
            "mistral",
            "https://api.mistral.ai/v1/audio/transcriptions",
            {"text": "你好，世界。"},
        ),
        (
            "deepgram",
            "https://api.deepgram.com/v1/listen",
            {
                "results": {
                    "channels": [{"alternatives": [{"transcript": "你好，世界。"}]}]
                }
            },
        ),
        (
            "azure",
            "https://eastus.api.cognitive.microsoft.com/speechtotext/transcriptions:transcribe",
            {"combinedPhrases": [{"text": "你好，世界。"}]},
        ),
    ],
)
async def test_cloud_provider_end_to_end(client, provider, endpoint, response):
    await configure(client, provider, language="zh-CN" if provider == "azure" else "zh")
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post(endpoint).mock(
            return_value=httpx.Response(200, json=response)
        )
        result = await client.post(
            "/api/v1/audio/transcriptions", files={"file": ("test.wav", wav())}
        )
    assert result.status_code == 200, result.text
    assert result.json() == {
        "text": "你好，世界。",
        "provider": provider,
        "audio_seconds": 0.1,
    }
    request = route.calls[0].request
    assert wav() in request.content
    if provider == "deepgram":
        assert request.headers["Authorization"] == "Token test-secret"
        assert request.url.params["language"] == "zh"
    elif provider == "azure":
        assert request.headers["Ocp-Apim-Subscription-Key"] == "test-secret"
        assert request.url.params["api-version"] == "2024-11-15"
        assert b"zh-CN" in request.content
    else:
        assert request.headers["Authorization"] == "Bearer test-secret"
        assert b'name="language"' in request.content


async def test_custom_openai_endpoint_without_key(client):
    await configure(
        client,
        api_key="",
        config={"base_url": "http://localhost:7777/v1", "model": "custom"},
    )
    with respx.mock as mock:
        route = mock.post("http://localhost:7777/v1/audio/transcriptions").mock(
            return_value=httpx.Response(200, json={"text": ""})
        )
        result = await client.post(
            "/api/v1/audio/transcriptions", files={"file": ("test.wav", wav())}
        )
    assert result.json()["text"] == ""
    assert "Authorization" not in route.calls[0].request.headers
    assert b"custom" in route.calls[0].request.content


@pytest.mark.parametrize(
    "failure,expected",
    [
        (httpx.Response(401, text="test-secret private upstream text"), 502),
        (httpx.Response(200, json={"bad": "payload"}), 502),
        (httpx.Response(200, json={"text": None}), 502),
        (httpx.Response(200, text="not-json"), 502),
        (httpx.ReadTimeout("private-url?key=test-secret"), 504),
        (httpx.ConnectError("test-secret"), 502),
    ],
)
async def test_provider_failures_are_sanitized(client, failure, expected):
    await configure(client)
    with respx.mock as mock:
        route = mock.post("https://api.openai.com/v1/audio/transcriptions")
        if isinstance(failure, Exception):
            route.mock(side_effect=failure)
        else:
            route.mock(return_value=failure)
        result = await client.post(
            "/api/v1/audio/transcriptions", files={"file": ("test.wav", wav())}
        )
    assert result.status_code == expected
    assert "test-secret" not in result.text


async def test_missing_key(client):
    await configure(client, "deepgram", api_key="")
    result = await client.post(
        "/api/v1/audio/transcriptions", files={"file": ("test.wav", wav())}
    )
    assert result.status_code == 400


async def test_explicit_cancellation_releases_capacity_before_returning(
    client, monkeypatch
):
    await configure(client)
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def pending(*_):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr("app.asr.service.cloud_transcribe", pending)
    identity = str(uuid4())
    active = asyncio.create_task(
        client.post(
            "/api/v1/audio/transcriptions",
            data={"request_id": identity},
            files={"file": ("test.wav", wav())},
        )
    )
    await started.wait()
    response = await client.delete(f"/api/v1/audio/transcriptions/{identity}")
    assert response.status_code == 200
    assert cancelled.is_set()
    assert (await active).status_code == 499
    monkeypatch.setattr(
        "app.asr.service.cloud_transcribe", AsyncMock(return_value="next")
    )
    response = await client.post(
        "/api/v1/audio/transcriptions", files={"file": ("test.wav", wav())}
    )
    assert response.json()["text"] == "next"


async def test_cancel_before_registration_is_idempotent(client, monkeypatch):
    await configure(client)
    dispatch = AsyncMock()
    monkeypatch.setattr("app.asr.service.cloud_transcribe", dispatch)
    identity = str(uuid4())
    for _ in range(2):
        assert (
            await client.delete(f"/api/v1/audio/transcriptions/{identity}")
        ).status_code == 200
    response = await client.post(
        "/api/v1/audio/transcriptions",
        data={"request_id": identity},
        files={"file": ("test.wav", wav())},
    )
    assert response.status_code == 499
    dispatch.assert_not_awaited()


async def test_local_preflight_and_no_implicit_download(client, monkeypatch, tmp_path):
    monkeypatch.setattr("app.asr.models.MODEL_DIR", tmp_path)
    await configure(client, "sensevoice")
    result = await client.post(
        "/api/v1/audio/transcriptions", files={"file": ("test.wav", wav())}
    )
    assert result.status_code == 409
    await configure(client, "sensevoice", language="fr")
    result = await client.post(
        "/api/v1/audio/transcriptions", files={"file": ("test.wav", wav())}
    )
    assert result.status_code == 400
    assert list(tmp_path.iterdir()) == []


async def test_worker_killed_and_reaped_on_cancel(monkeypatch):
    started = asyncio.Event()
    monkeypatch.setattr("app.asr.models.resolve_paths", lambda _: {})

    class Process:
        returncode = None
        killed = False
        reaped = False

        async def communicate(self, _):
            started.set()
            await asyncio.Event().wait()

        def kill(self):
            self.killed = True
            self.returncode = -9

        async def wait(self):
            self.reaped = True

    process = Process()
    monkeypatch.setattr(
        asyncio, "create_subprocess_exec", AsyncMock(return_value=process)
    )
    work = asyncio.create_task(local_transcribe(ASRConfig(), wav()))
    await started.wait()
    work.cancel()
    with pytest.raises(asyncio.CancelledError):
        await work
    assert process.killed and process.reaped


async def test_busy_and_disconnect_cleanup(monkeypatch):
    app = FastAPI()
    request = Request({"type": "http", "app": app})
    request.is_disconnected = AsyncMock(return_value=True)
    cancelled = asyncio.Event()

    async def pending(*_):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr("app.asr.service.local_transcribe", pending)
    app.state.asr_busy = True
    with pytest.raises(HTTPException) as busy:
        await transcribe(request, ASRConfig(), wav())
    assert busy.value.status_code == 429
    app.state.asr_busy = False
    with pytest.raises(HTTPException) as disconnected:
        await transcribe(request, ASRConfig(), wav())
    assert disconnected.value.status_code == 499
    assert not app.state.asr_busy


async def test_deadline_cancels_work_and_releases_capacity(monkeypatch):
    app = FastAPI()
    request = Request({"type": "http", "app": app})
    request.is_disconnected = AsyncMock(return_value=False)
    cancelled = asyncio.Event()

    async def pending(*_):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr("app.asr.service.local_transcribe", pending)
    monkeypatch.setattr("app.asr.service.TRANSCRIPTION_TIMEOUT", 0.02)
    with pytest.raises(HTTPException) as error:
        await transcribe(request, ASRConfig(), wav())
    assert error.value.status_code == 504
    assert cancelled.is_set()
    assert not app.state.asr_busy


@pytest.mark.parametrize(
    "output,code", [(b"garbage", 0), (b"[]", 0), (b'{"text": null}', 0), (b"", 1)]
)
async def test_native_failure_and_protocol_errors_are_sanitized(
    monkeypatch, output, code
):
    monkeypatch.setattr("app.asr.models.resolve_paths", lambda _: {})

    class Process:
        returncode = code

        async def communicate(self, _):
            return output, None

        async def wait(self):
            pass

    monkeypatch.setattr(
        asyncio, "create_subprocess_exec", AsyncMock(return_value=Process())
    )
    with pytest.raises(HTTPException) as error:
        await local_transcribe(ASRConfig(), wav())
    assert error.value.status_code == 503


def test_wave_duration():
    assert validate_audio(wav(seconds=1)) == 1
