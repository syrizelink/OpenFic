"""Base types for background job definitions."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from builtins import type as builtin_type
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from app.background.runtime.context import JobContext


class EmptyJobResult(BaseModel):
    """Default empty result model for jobs that do not return data."""

    model_config = ConfigDict(extra="allow")


JobHandler = Callable[["JobContext"], Awaitable[dict[str, Any] | BaseModel | None]]
JobLifecycleHook = Callable[["JobContext", str], Awaitable[None]]


@dataclass(frozen=True)
class JobDefinition:
    """Discoverable definition for one background job type."""

    type: str
    name: str
    description: str
    input_model: builtin_type[BaseModel]
    handler: JobHandler
    result_model: builtin_type[BaseModel] = EmptyJobResult
    on_failed: JobLifecycleHook | None = None
    on_timeout: JobLifecycleHook | None = None
    on_cancelled: JobLifecycleHook | None = None
    default_queue: str = "default"
    default_timeout_seconds: int = 300
    default_max_attempts: int = 1
    supports_cancel: bool = False
    supports_batch: bool = False
    progress_mode: str = "steps"
