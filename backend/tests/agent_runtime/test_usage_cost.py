# -*- coding: utf-8 -*-
"""Agent LLM usage cost tests."""

from app.agent_runtime.usage_cost import (
    calculate_llm_call_cost,
    extract_cache_read_tokens,
    extract_cache_write_tokens,
)
from app.agent_runtime.runner.session_runner import SessionRunner


def test_calculate_llm_call_cost_splits_cached_tokens() -> None:
    cost = calculate_llm_call_cost(
        token_input=1_000,
        token_output=200,
        token_cache=200,
        token_cache_write=100,
        input_price=2.0,
        output_price=8.0,
        cache_read_price=0.5,
        cache_write_price=1.0,
    )

    assert cost == 0.0032


def test_extract_cache_write_tokens_accepts_provider_usage_shapes() -> None:
    assert extract_cache_write_tokens(
        {
            "input_tokens": 20,
            "cache_creation_input_tokens": 7,
        }
    ) == 7
    assert extract_cache_write_tokens(
        {
            "input_tokens": 20,
            "input_token_details": {"cache_write": 5},
        }
    ) == 5


def test_extract_cache_read_tokens_falls_back_when_top_level_value_is_zero() -> None:
    assert extract_cache_read_tokens(
        {
            "cache_read_tokens": 0,
            "input_token_details": {"cache_read": 7},
        }
    ) == 7


def test_session_runner_includes_cache_write_price_in_call_cost() -> None:
    runner = SessionRunner(
        session_id="session-cost",
        task_id="task-cost",
        model_config={
            "max_context_tokens": 128000,
            "input_price": 2.0,
            "output_price": 8.0,
            "cache_read_price": 0.5,
            "cache_write_price": 1.0,
        },
    )

    normalized = runner._normalize_usage_event(
        {
            "usage": {
                "input_tokens": 1_000,
                "output_tokens": 200,
                "input_token_details": {"cache_read": 200, "cache_write": 100},
            }
        }
    )

    assert normalized["token_cache"] == 200
    assert normalized["cost"] == 0.0032
