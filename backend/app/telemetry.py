# -*- coding: utf-8 -*-
"""
PostHog 错误遥测。

统一捕获后端未处理异常并上报。仅上报异常类型、消息、堆栈与请求上下文，
不上报请求体、API key 或用户内容；上报失败静默忽略，不影响应用运行。
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
    """当前是否启用错误遥测。"""
    return _enabled


def parse_telemetry_enabled(raw_value: str | None) -> bool:
    """将 DB 中的布尔设置值解析为布尔，缺省时默认开启。"""
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
    """设置遥测开关，并同步初始化/销毁 PostHog 客户端。"""
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
    """基于加密密钥派生稳定匿名标识，不泄露密钥本身。"""
    return hashlib.sha256(settings.encryption_key.encode("utf-8")).hexdigest()[:32]


def capture_exception(
    exception: BaseException,
    *,
    properties: dict[str, Any] | None = None,
) -> None:
    """上报单个异常，失败时静默忽略。"""
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
        logger.debug("PostHog 错误遥测上报失败（已忽略）")


def _error_sink(message: Any) -> None:
    """loguru sink：捕获 ERROR 级且带异常的日志并上报。"""
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
    """安装遥测 sink（幂等）。客户端由 set_telemetry_enabled 惰性创建。"""
    global _sink_id
    if _sink_id is not None:
        return
    _sink_id = logger.add(_error_sink, level="ERROR")


def shutdown() -> None:
    """关闭遥测客户端，冲刷待发送事件。"""
    global _client
    if _client is not None:
        try:
            _client.shutdown()
        except Exception:
            pass
        _client = None
