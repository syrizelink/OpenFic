from collections.abc import Mapping
from typing import Any


def without_api_key(model_config: Mapping[str, Any]) -> dict[str, Any]:
    """Return the model configuration safe to persist in graph state."""
    persisted_config = dict(model_config)
    persisted_config.pop("api_key", None)
    return persisted_config


def to_client_model_config(model_config: Mapping[str, Any]) -> dict[str, Any]:
    """Remove Agent runtime-only fields before constructing a model client."""
    client_config = dict(model_config)
    client_config.pop("model_record_id", None)
    for key in ("input_price", "output_price", "cache_read_price", "cache_write_price"):
        client_config.pop(key, None)
    return client_config
