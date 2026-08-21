"""LLM usage normalization helpers for cost accounting."""

from collections.abc import Mapping
from typing import Any


def _non_negative_int(value: Any) -> int:
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0


def _nested_usage_value(usage: Mapping[str, Any], keys: tuple[str, ...]) -> int:
    for key in keys:
        if key in usage:
            value = _non_negative_int(usage[key])
            if value > 0:
                return value

    for details_key in ("input_token_details", "prompt_tokens_details"):
        details = usage.get(details_key)
        if not isinstance(details, Mapping):
            continue
        for key in keys:
            if key in details:
                value = _non_negative_int(details[key])
                if value > 0:
                    return value
    return 0


def extract_cache_read_tokens(usage: Mapping[str, Any] | None) -> int:
    if not isinstance(usage, Mapping):
        return 0
    return _nested_usage_value(
        usage,
        ("cache_read_tokens", "cache_read_input_tokens", "cache_read", "cached_tokens"),
    )


def extract_cache_write_tokens(usage: Mapping[str, Any] | None) -> int:
    if not isinstance(usage, Mapping):
        return 0
    return _nested_usage_value(
        usage,
        (
            "cache_write_tokens",
            "cache_creation_input_tokens",
            "cache_write",
            "cache_creation",
        ),
    )


def calculate_llm_call_cost(
    *,
    token_input: int,
    token_output: int,
    token_cache: int,
    token_cache_write: int,
    input_price: float,
    output_price: float,
    cache_read_price: float,
    cache_write_price: float,
) -> float:
    """Calculate one call's cost in dollars from prices per million tokens."""
    billable_input = max(token_input - token_cache - token_cache_write, 0)
    return (
        billable_input * max(input_price, 0.0)
        + max(token_output, 0) * max(output_price, 0.0)
        + max(token_cache, 0) * max(cache_read_price, 0.0)
        + max(token_cache_write, 0) * max(cache_write_price, 0.0)
    ) / 1_000_000
