"""Dispatch background jobs to registered handlers."""

from pydantic import ValidationError

from app.background.runtime.context import JobContext
from app.background.runtime.registry import get_job_registry


class UnknownJobTypeError(ValueError):
    """Raised when no handler is registered for a job type."""


class InvalidJobPayloadError(ValueError):
    """Raised when a job payload does not match its definition."""


async def dispatch_job(context: JobContext) -> dict | None:
    definition = get_job_registry().get(context.job_type)
    if definition is None:
        raise UnknownJobTypeError(f"未注册的后台任务类型: {context.job_type}")

    try:
        payload = definition.input_model.model_validate(context.input)
    except ValidationError as exc:
        raise InvalidJobPayloadError(f"后台任务参数无效: {exc}") from exc

    context.definition = definition
    context.payload = payload
    await context.check_cancelled()
    result = await definition.handler(context)
    await context.check_cancelled()
    if result is None:
        return None
    result_model = definition.result_model.model_validate(result)
    return result_model.model_dump()
