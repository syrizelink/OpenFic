"""LLM 调用超时保护与失败重试机制。

单一入口 ``invoke_model_with_retry`` 负责：错误分类、退避计算、
重试事件发布与空响应重放；超时通过 ``_TimedStream`` 包装流式
迭代器实现 chunk 空闲超时。
"""

from __future__ import annotations

import asyncio
import ssl
from collections.abc import Awaitable, Callable, Iterator, Mapping
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
    """流式调用正常结束但未产出任何响应。"""


class LLMStreamTimeoutError(TimeoutError):
    """流式调用在 chunk 空闲时超时。"""


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
_TLS_CERTIFICATE_PATTERNS = (
    "certificate verify failed",
    "certificate_verify_failed",
    "certificate validation failed",
    "certificate validation error",
    "certificate has expired",
    "certificate expired",
    "self-signed certificate",
    "self signed certificate",
    "unable to get local issuer certificate",
    "unable to verify the first certificate",
    "hostname mismatch",
    "hostname does not match",
    "hostname doesn't match",
    "does not match certificate",
    "doesn't match certificate",
)


def _contains_any(message: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in message for pattern in patterns)


def _exception_chain(exc: BaseException) -> Iterator[BaseException]:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        next_exception = current.__cause__
        if next_exception is None and not current.__suppress_context__:
            next_exception = current.__context__
        current = next_exception


def format_error_message(exc: BaseException) -> str:
    """Include distinct chained causes in the user-visible error summary."""
    message = str(exc).strip() or type(exc).__name__
    represented_messages = [message.casefold()]
    cause_details: list[str] = []
    for cause in _exception_chain(exc):
        if cause is exc:
            continue
        cause_message = str(cause).strip()
        if cause_message and any(
            cause_message.casefold() in represented
            for represented in represented_messages
        ):
            continue
        detail = type(cause).__name__
        if cause_message:
            detail = f"{detail}: {cause_message}"
            represented_messages.append(cause_message.casefold())
        cause_details.append(detail)
    if not cause_details:
        return message
    return f"{message} (caused by {'; caused by '.join(cause_details)})"


def _is_tls_certificate_error(exc: BaseException) -> bool:
    for cause in _exception_chain(exc):
        cause_name = type(cause).__name__.lower().replace("_", "")
        if isinstance(cause, ssl.SSLCertVerificationError) or any(
            name in cause_name
            for name in ("certverificationerror", "certificateerror")
        ):
            return True
        if cause is exc and _error_status_code(exc) is not None:
            continue
        if _contains_any(str(cause).lower(), _TLS_CERTIFICATE_PATTERNS):
            return True
    return False


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
    """按错误类型决定是否重试及所属分类。

    可重试：5xx、限流、超时、网络类、空响应。
    不可重试：认证、配额、上下文溢出、压缩失败、用户中断及未分类错误。
    """
    if isinstance(exc, EmptyResponseError):
        return RetryOutcome(RetryDecision.RETRY, RetryCategory.EMPTY_RESPONSE)
    if isinstance(exc, CompactionError):
        return RetryOutcome(RetryDecision.NO_RETRY, RetryCategory.CONTEXT_OVERFLOW)
    if isinstance(exc, asyncio.CancelledError):
        return RetryOutcome(RetryDecision.NO_RETRY, RetryCategory.OTHER)
    if _is_tls_certificate_error(exc):
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
    """从错误响应头解析 retry-after-ms / retry-after（秒或 HTTP 日期）。"""
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
    """计算下次重试等待秒数：retry-after 头优先，否则指数退避。"""
    retry_after_ms = extract_retry_after_ms(exc)
    if retry_after_ms is not None:
        return retry_after_ms / 1000.0
    return min(base_interval * (2.0 ** (attempt - 1)), max_interval)


class _TimedStream:
    """为流式迭代器叠加 chunk 空闲超时与总时长超时。"""

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
                "error_message": format_error_message(exc),
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
    """以流级重试调用 LLM：每次重试都重新发起完整请求。

    空响应（EmptyResponseError）单独计数重放；其余错误按
    ``classify_error`` 分类，不可重试或达到上限时抛出原错误。
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
