"""Perlindungan batas waktu pemanggilan LLM dan mekanisme coba ulang saat gagal.

Satu pintu masuk ``invoke_model_with_retry`` bertanggung jawab atas: klasifikasi
error, perhitungan backoff, penerbitan event coba ulang, dan pemutaran ulang
respons kosong; batas waktu diwujudkan dengan membungkus iterator aliran memakai
``_TimedStream`` untuk batas waktu chunk yang menganggur.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from enum import Enum
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage

from app.agent_runtime.context.compaction.service import CompactionError

RetryEventSink = Callable[[dict[str, Any]], Awaitable[None]]
InvokeCallable = Callable[..., Awaitable[AIMessage]]


class RetryDecision(Enum):
    RETRY = "retry"
    NO_RETRY = "no_retry"


class RetryCategory(str, Enum):
    HTTP = "http"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    NETWORK = "network"
    EMPTY_RESPONSE = "empty_response"
    AUTH = "auth"
    QUOTA = "quota"
    CONTEXT_OVERFLOW = "context_overflow"
    OTHER = "other"


@dataclass(frozen=True)
class RetryOutcome:
    decision: RetryDecision
    category: RetryCategory


class EmptyResponseError(RuntimeError):
    """Pemanggilan aliran berakhir normal tetapi tidak menghasilkan respons apa
    pun."""


class LLMStreamTimeoutError(TimeoutError):
    """Pemanggilan aliran melewati batas waktu saat chunk menganggur."""


@dataclass(frozen=True)
class LLMInvokeSettings:
    connect_timeout: float = 10.0
    chunk_timeout: float = 120.0
    max_attempts: int = 5
    retry_base_interval: float = 2.0
    retry_max_interval: float = 30.0
    empty_response_retries: int = 2


def load_llm_invoke_settings() -> LLMInvokeSettings:
    from app.settings import settings

    return LLMInvokeSettings(
        connect_timeout=settings.llm_connect_timeout,
        chunk_timeout=settings.llm_chunk_timeout,
        max_attempts=settings.llm_retry_max_attempts,
        retry_base_interval=settings.llm_retry_base_interval,
        retry_max_interval=settings.llm_retry_max_interval,
        empty_response_retries=settings.llm_empty_response_retries,
    )


_RATE_LIMIT_PATTERNS = (
    "rate limit",
    "rate_limit",
    "too many requests",
    "rate increased too quickly",
    "exhausted",
    "unavailable",
    "overloaded",
)
_AUTH_PATTERNS = (
    "invalid api key",
    "incorrect api key",
    "api key not found",
    "authentication",
    "unauthorized",
)
_QUOTA_PATTERNS = (
    "quota",
    "insufficient",
    "billing",
    "payment required",
)
_CONTEXT_PATTERNS = (
    "context length",
    "maximum context",
    "context window",
    "token limit",
    "prompt is too long",
    "too many tokens",
)


def _contains_any(message: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in message for pattern in patterns)


def _error_status_code(exc: BaseException) -> int | None:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    return status_code if isinstance(status_code, int) else None


def _error_headers(exc: BaseException) -> dict[str, str]:
    raw_headers: Any = None
    response = getattr(exc, "response", None)
    if response is not None:
        raw_headers = getattr(response, "headers", None)
    if raw_headers is None:
        raw_headers = getattr(exc, "headers", None)
    if not isinstance(raw_headers, Mapping):
        return {}
    return {str(key).lower(): str(value) for key, value in raw_headers.items()}


def classify_error(exc: BaseException) -> RetryOutcome:
    """Menentukan apakah error perlu dicoba ulang beserta klasifikasinya.

    Dapat dicoba ulang: 5xx, pembatasan laju, batas waktu, jenis jaringan, respons
    kosong.
    Tidak dapat dicoba ulang: autentikasi, kuota, konteks meluap, pemadatan gagal,
    pembatalan oleh pengguna, dan error yang tidak terklasifikasi.
    """
    if isinstance(exc, EmptyResponseError):
        return RetryOutcome(RetryDecision.RETRY, RetryCategory.EMPTY_RESPONSE)
    if isinstance(exc, CompactionError):
        return RetryOutcome(RetryDecision.NO_RETRY, RetryCategory.CONTEXT_OVERFLOW)
    if isinstance(exc, asyncio.CancelledError):
        return RetryOutcome(RetryDecision.NO_RETRY, RetryCategory.OTHER)

    status_code = _error_status_code(exc)
    message = str(exc).lower()
    exc_name = type(exc).__name__.lower()
    if status_code is not None:
        if 500 <= status_code < 600:
            return RetryOutcome(RetryDecision.RETRY, RetryCategory.HTTP)
        if status_code in (401, 403):
            return RetryOutcome(RetryDecision.NO_RETRY, RetryCategory.AUTH)
        if status_code == 429:
            if _contains_any(message, _QUOTA_PATTERNS):
                return RetryOutcome(RetryDecision.NO_RETRY, RetryCategory.QUOTA)
            return RetryOutcome(RetryDecision.RETRY, RetryCategory.RATE_LIMIT)

    if _contains_any(message, _RATE_LIMIT_PATTERNS):
        if _contains_any(message, _QUOTA_PATTERNS):
            return RetryOutcome(RetryDecision.NO_RETRY, RetryCategory.QUOTA)
        return RetryOutcome(RetryDecision.RETRY, RetryCategory.RATE_LIMIT)
    if _contains_any(message, _AUTH_PATTERNS) or "autherror" in exc_name:
        return RetryOutcome(RetryDecision.NO_RETRY, RetryCategory.AUTH)
    if _contains_any(message, _QUOTA_PATTERNS):
        return RetryOutcome(RetryDecision.NO_RETRY, RetryCategory.QUOTA)
    if _contains_any(message, _CONTEXT_PATTERNS):
        return RetryOutcome(RetryDecision.NO_RETRY, RetryCategory.CONTEXT_OVERFLOW)

    if isinstance(exc, TimeoutError) or "timeout" in exc_name:
        return RetryOutcome(RetryDecision.RETRY, RetryCategory.TIMEOUT)
    if isinstance(exc, ConnectionError) or "connection" in exc_name:
        return RetryOutcome(RetryDecision.RETRY, RetryCategory.NETWORK)
    if "ratelimit" in exc_name:
        return RetryOutcome(RetryDecision.RETRY, RetryCategory.RATE_LIMIT)

    return RetryOutcome(RetryDecision.NO_RETRY, RetryCategory.OTHER)


def extract_retry_after_ms(exc: BaseException) -> float | None:
    """Mengurai retry-after-ms / retry-after dari header respons error (detik atau
    tanggal HTTP)."""
    headers = _error_headers(exc)
    if not headers:
        return None
    ms_value = headers.get("retry-after-ms")
    if ms_value:
        try:
            return float(ms_value)
        except ValueError:
            return None
    value = headers.get("retry-after")
    if not value:
        return None
    try:
        return float(value) * 1000.0
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return max((parsed - datetime.now(UTC)).total_seconds() * 1000.0, 0.0)
    except (TypeError, ValueError, OverflowError):
        return None


def compute_retry_delay(
    exc: BaseException,
    *,
    attempt: int,
    base_interval: float,
    max_interval: float,
) -> float:
    """Menghitung jumlah detik tunggu sebelum coba ulang berikutnya: header
    retry-after diprioritaskan, jika tidak memakai backoff eksponensial."""
    retry_after_ms = extract_retry_after_ms(exc)
    if retry_after_ms is not None:
        return retry_after_ms / 1000.0
    return min(base_interval * (2.0 ** (attempt - 1)), max_interval)


class _TimedStream:
    """Menambahkan batas waktu chunk menganggur dan batas waktu total pada iterator
    aliran."""

    def __init__(
        self,
        astream: Any,
        *,
        chunk_timeout: float | None,
    ) -> None:
        self._iterator = astream.__aiter__()
        self._chunk_timeout = chunk_timeout

    def __aiter__(self) -> _TimedStream:
        return self

    async def __anext__(self) -> Any:
        timeout = self._chunk_timeout
        if timeout is None:
            return await self._iterator.__anext__()
        try:
            return await asyncio.wait_for(self._iterator.__anext__(), timeout=timeout)
        except TimeoutError as exc:
            raise LLMStreamTimeoutError(
                f"LLM stream chunk idle timeout after {timeout}s"
            ) from exc


async def _emit_retry_event(
    sink: RetryEventSink,
    *,
    session_id: str | None,
    node: str | None,
    attempt: int,
    max_attempts: int,
    exc: BaseException,
    category: RetryCategory,
    retry_in_ms: int,
) -> None:
    try:
        await sink(
            {
                "session_id": session_id,
                "node": node,
                "attempt": attempt,
                "max_attempts": max_attempts,
                "error_type": exc.__class__.__name__,
                "error_message": str(exc),
                "error_category": category.value,
                "retry_in_ms": retry_in_ms,
            }
        )
    except Exception:
        return


async def invoke_model_with_retry(
    model: Any,
    messages: list[BaseMessage],
    *,
    invoke: InvokeCallable,
    settings: LLMInvokeSettings,
    session_id: str | None = None,
    node: str | None = None,
    retry_event_sink: RetryEventSink | None = None,
) -> AIMessage:
    """Memanggil LLM dengan coba ulang pada tingkat aliran: setiap percobaan ulang
    mengirim permintaan lengkap dari awal.

    Respons kosong (EmptyResponseError) dihitung dan diputar ulang secara terpisah;
    error lainnya diklasifikasikan oleh ``classify_error``, dan error aslinya
    dimunculkan bila tidak dapat dicoba ulang atau batas maksimum tercapai.
    """
    attempt = 1
    empty_response_retries = 0
    while True:
        try:
            return await invoke(
                model,
                messages,
                chunk_timeout=settings.chunk_timeout,
            )
        except asyncio.CancelledError:
            raise
        except EmptyResponseError as caught:
            if (
                empty_response_retries >= settings.empty_response_retries
                or attempt >= settings.max_attempts
            ):
                raise
            empty_response_retries += 1
            exc = caught
            category = RetryCategory.EMPTY_RESPONSE
        except Exception as caught:
            outcome = classify_error(caught)
            if (
                outcome.decision is RetryDecision.NO_RETRY
                or attempt >= settings.max_attempts
            ):
                raise
            exc = caught
            category = outcome.category
        delay = compute_retry_delay(
            exc,
            attempt=attempt,
            base_interval=settings.retry_base_interval,
            max_interval=settings.retry_max_interval,
        )
        if retry_event_sink is not None:
            await _emit_retry_event(
                retry_event_sink,
                session_id=session_id,
                node=node,
                attempt=attempt + 1,
                max_attempts=settings.max_attempts,
                exc=exc,
                category=category,
                retry_in_ms=int(delay * 1000),
            )
        await asyncio.sleep(delay)
        attempt += 1
