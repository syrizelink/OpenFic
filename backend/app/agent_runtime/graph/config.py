import asyncio
from collections.abc import Mapping
from typing import Any, cast

from langchain_core.runnables import RunnableConfig


def build_child_config(
    parent_config: RunnableConfig | None,
    runtime_state: Mapping[str, Any],
    **extra_configurable: Any,
) -> RunnableConfig:
    config = cast(RunnableConfig, dict(parent_config or {}))
    configurable = dict(config.get("configurable") or {})
    configurable["runtime_state"] = dict(runtime_state)
    for key, value in extra_configurable.items():
        if value is not None:
            configurable[key] = value
    config["configurable"] = configurable
    return config


def get_inject_queue(
    config: RunnableConfig | None,
) -> asyncio.Queue[tuple[str | None, str, str]] | None:
    if not isinstance(config, dict):
        return None
    configurable = config.get("configurable")
    if not isinstance(configurable, dict):
        return None
    value = configurable.get("inject_queue")
    return value if isinstance(value, asyncio.Queue) else None
