import logging
import time
from dataclasses import dataclass
from http import HTTPStatus
from inspect import getsourcelines
from types import CodeType
from typing import Callable, MutableMapping, cast

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


logging.getLogger("uvicorn.access").disabled = True


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        started_at = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - started_at) * 1000
            self._log_request(request, 500, duration_ms)
            logger.opt(exception=True).debug(
                "request failed: {} {}", request.method, request.url.path
            )
            raise

        duration_ms = (time.perf_counter() - started_at) * 1000
        self._log_request(request, response.status_code, duration_ms)
        return response

    def _log_request(
        self, request: Request, status_code: int, duration_ms: float
    ) -> None:
        path = request.url.path
        access_logger = logger.bind(
            method=request.method,
            path=path,
            status_code=status_code,
            duration_ms=round(duration_ms, 2),
        )
        endpoint_location = get_endpoint_location(request)
        if endpoint_location is not None:
            access_logger = access_logger.patch(
                lambda record: _patch_endpoint_location(
                    cast("MutableMapping[str, object]", record), endpoint_location
                )
            )
        _log_at_level(
            access_logger, status_code,
            format_access_log(request.method, path, status_code, duration_ms),
        )


@dataclass(frozen=True)
class EndpointLocation:
    name: str
    function: str
    line: int


def format_access_log(
    method: str, path: str, status_code: int, duration_ms: float
) -> str:
    return f"{method} {path} {status_code} {_get_status_phrase(status_code)} {duration_ms:.2f}ms"


def get_endpoint_location(request: Request) -> EndpointLocation | None:
    endpoint = request.scope.get("endpoint")
    if not callable(endpoint) or not hasattr(endpoint, "__code__"):
        return None
    return get_callable_location(endpoint)


def _patch_endpoint_location(
    record: MutableMapping[str, object], endpoint_location: EndpointLocation
) -> None:
    record["name"] = endpoint_location.name
    record["function"] = endpoint_location.function
    record["line"] = endpoint_location.line


def get_callable_location(endpoint: Callable[..., object]) -> EndpointLocation:
    code = _get_callable_code(endpoint)
    line = code.co_firstlineno
    try:
        _, line = getsourcelines(endpoint)
    except (OSError, TypeError):
        pass
    return EndpointLocation(
        name=endpoint.__module__,
        function=endpoint.__qualname__,
        line=line,
    )


def _get_callable_code(endpoint: Callable[..., object]) -> CodeType:
    return endpoint.__code__  # type: ignore[attr-defined]


def _log_at_level(bound_logger, status_code: int, message: str) -> None:
    if status_code >= 500:
        bound_logger.error(message)
    elif status_code >= 400:
        bound_logger.warning(message)
    else:
        bound_logger.info(message)


def _get_status_phrase(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return ""
