from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, cast

from loguru import logger

ToolErrorCode = Literal[
    "validation_error",
    "not_found",
    "conflict",
    "permission_denied",
    "malformed_tool_call",
    "tool_not_found",
    "limit_exceeded",
    "dependency_unavailable",
    "execution_failed",
]

_TOOL_ERROR_CODES: set[str] = {
    "validation_error",
    "not_found",
    "conflict",
    "permission_denied",
    "malformed_tool_call",
    "tool_not_found",
    "limit_exceeded",
    "dependency_unavailable",
    "execution_failed",
}
_FAILURE_FIELDS = {
    "type",
    "success",
    "code",
    "message",
    "error",
    "reason",
    "trace",
    "metadata",
    "data",
    "recoverable",
    "raw_args",
    "tool_call_id",
    "tool_name",
}


def _error_code(value: object) -> ToolErrorCode:
    if isinstance(value, str) and value in _TOOL_ERROR_CODES:
        return cast(ToolErrorCode, value)
    return "execution_failed"


@dataclass(frozen=True)
class ToolFailure:
    code: ToolErrorCode
    message: str
    trace: dict[str, str] = field(default_factory=dict)

    def to_result(self, extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
        result = dict(extra or {})
        result.update(
            {
                "type": "fail",
                "success": False,
                "code": self.code,
                "message": self.message,
            }
        )
        return result


class ToolExecutionError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: ToolErrorCode = "execution_failed",
    ) -> None:
        self.code = _error_code(code)
        super().__init__(message)


def tool_failure_from_exception(
    error: BaseException,
    *,
    code: ToolErrorCode | None = None,
    source: str,
) -> ToolFailure:
    message = str(error).strip() or "工具执行失败"
    return ToolFailure(
        code=_error_code(code or getattr(error, "code", None)),
        message=message,
        trace={"source": source, "exception_type": type(error).__name__},
    )


def tool_failure_from_error(
    error: object,
    *,
    code: ToolErrorCode | None = None,
    source: str,
) -> ToolFailure:
    if isinstance(error, ToolExecutionError):
        return tool_failure_from_exception(error, code=code, source=source)
    return ToolFailure(
        code=_error_code(code),
        message="工具执行失败",
        trace={
            "source": source,
            **(
                {"exception_type": type(error).__name__}
                if isinstance(error, BaseException)
                else {}
            ),
        },
    )


def tool_failure_from_result(value: object) -> tuple[ToolFailure, dict[str, Any]] | None:
    if isinstance(value, str):
        try:
            payload = json.loads(value)
        except json.JSONDecodeError:
            return None
    elif isinstance(value, Mapping):
        payload = dict(value)
    else:
        return None

    if not isinstance(payload, dict) or payload.get("type") == "control":
        return None

    is_failure = (
        payload.get("type") == "fail"
        or payload.get("success") is False
        or isinstance(payload.get("error"), str)
    )
    if not is_failure:
        return None

    message = payload.get("message") or payload.get("error")
    if not isinstance(message, str) or not message.strip():
        message = "工具执行失败"

    extra = {key: item for key, item in payload.items() if key not in _FAILURE_FIELDS}
    failure = ToolFailure(
        code=_error_code(payload.get("code")),
        message=message.strip(),
        trace={"source": "tool_result"},
    )
    return failure, extra


def serialize_tool_failure(
    failure: ToolFailure,
    extra: Mapping[str, Any] | None = None,
) -> str:
    return json.dumps(failure.to_result(extra), ensure_ascii=False)


def normalize_tool_failure_result(value: object) -> tuple[object, ToolFailure | None]:
    normalized = tool_failure_from_result(value)
    if normalized is None:
        return value, None
    failure, extra = normalized
    return serialize_tool_failure(failure, extra), failure


def log_tool_failure(
    failure: ToolFailure,
    *,
    tool_name: str,
    tool_call_id: str | None,
    exception: BaseException | None = None,
) -> None:
    logger_context = logger.bind(
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        error_code=failure.code,
        **failure.trace,
    )
    if exception is not None:
        logger_context.error("Agent 工具执行失败")
        return
    logger_context.warning("Agent 工具执行失败: {}", failure.message)
