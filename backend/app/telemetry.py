# -*- coding: utf-8 -*-
"""
Telemetri error PostHog.

Menangkap eksepsi backend yang tidak tertangani secara terpusat lalu melaporkannya. Yang
dilaporkan hanya tipe eksepsi, pesan, stack, dan konteks permintaan,
bukan body permintaan, API key, atau isi milik pengguna; kegagalan pelaporan diabaikan
tanpa suara dan tidak memengaruhi jalannya aplikasi.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from loguru import logger

from app.settings import settings

SETTING_KEY_TELEMETRY_ENABLED = "telemetry_enabled"
DEFAULT_TELEMETRY_ENABLED = True

_client: Any = None
_enabled: bool = bool(settings.posthog_api_key)
_sink_id: int | None = None

_MESSAGE_MAX_LENGTH = 2000


def is_telemetry_enabled() -> bool:
    """Apakah telemetri error sedang aktif."""
    return _enabled


def parse_telemetry_enabled(raw_value: str | None) -> bool:
    """Mengurai nilai setelan boolean dari DB menjadi boolean, aktif secara bawaan bila
    tidak ada nilainya."""
    if raw_value is None or raw_value == "":
        return DEFAULT_TELEMETRY_ENABLED
    try:
        return bool(json.loads(raw_value))
    except json.JSONDecodeError:
        normalized = raw_value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
        return DEFAULT_TELEMETRY_ENABLED


def set_telemetry_enabled(enabled: bool) -> None:
    """Mengatur sakelar telemetri sekaligus menginisialisasi/melepas klien PostHog."""
    global _enabled
    _enabled = bool(enabled) and bool(settings.posthog_api_key)
    _ensure_client()


def _ensure_client() -> None:
    global _client
    if _enabled and _client is None:
        try:
            from posthog import Posthog

            _client = Posthog(settings.posthog_api_key, host=settings.posthog_host)
        except Exception:
            _client = None
    elif not _enabled and _client is not None:
        _client = None


def _anonymous_distinct_id() -> str:
    """Menurunkan identitas anonim yang stabil dari kunci enkripsi tanpa membocorkan kuncinya."""
    return hashlib.sha256(settings.encryption_key.encode("utf-8")).hexdigest()[:32]


def capture_exception(
    exception: BaseException,
    *,
    properties: dict[str, Any] | None = None,
) -> None:
    """Melaporkan satu eksepsi, kegagalan diabaikan tanpa suara."""
    if not _enabled or _client is None:
        return
    try:
        payload: dict[str, Any] = {"source": "backend"}
        if properties:
            payload.update(properties)
        _client.capture_exception(
            exception,
            distinct_id=_anonymous_distinct_id(),
            properties=payload,
        )
    except Exception:
        logger.debug("Pelaporan telemetri error PostHog gagal (diabaikan)")


def _error_sink(message: Any) -> None:
    """loguru sink: menangkap log level ERROR yang membawa eksepsi lalu melaporkannya."""
    if not _enabled or _client is None:
        return
    record = message.record
    if record["level"].no < logging.ERROR:
        return
    if record["exception"] is None:
        return
    name = record.get("name") or ""
    if "posthog" in name or "uvicorn" in name:
        return

    _exc_type, exc_value, _traceback = record["exception"]
    extra = record.get("extra") or {}
    properties: dict[str, Any] = {
        "source": "backend",
        "logger": name,
        "log_message": str(record["message"])[:_MESSAGE_MAX_LENGTH],
    }
    if extra.get("request_method"):
        properties["request_method"] = extra["request_method"]
    if extra.get("request_path"):
        properties["request_path"] = extra["request_path"]

    capture_exception(exc_value, properties=properties)


def install_telemetry_sink() -> None:
    """Memasang sink telemetri (idempoten). Klien dibuat secara lazy oleh
    set_telemetry_enabled."""
    global _sink_id
    if _sink_id is not None:
        return
    _sink_id = logger.add(_error_sink, level="ERROR")


def shutdown() -> None:
    """Menutup klien telemetri dan mengosongkan event yang menunggu dikirim."""
    global _client
    if _client is not None:
        try:
            _client.shutdown()
        except Exception:
            pass
        _client = None
