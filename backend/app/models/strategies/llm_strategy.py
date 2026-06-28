# -*- coding: utf-8 -*-
"""
LLM Strategy - LLM模型策略。

处理LLM模型的参数规范化和校验。
"""

from typing import Any

from app.models.strategies.base import BaseStrategy, StandardizedConfig


class LLMStrategy(BaseStrategy):
    """LLM模型策略，处理chat completion相关的参数。"""

    def normalize_parameters(self, raw_params: dict[str, Any]) -> dict[str, Any]:
        """
        规范化LLM参数。

        Args:
            raw_params: 原始参数（可能包含temperature、top_p等）。

        Returns:
            规范化后的参数字典。
        """
        normalized = {}

        # Temperature: 0.0-2.0
        if "temperature" in raw_params and raw_params["temperature"] is not None:
            temp = float(raw_params["temperature"])
            normalized["temperature"] = max(0.0, min(2.0, temp))

        # Top P: 0.0-1.0
        if "top_p" in raw_params and raw_params["top_p"] is not None:
            top_p = float(raw_params["top_p"])
            normalized["top_p"] = max(0.0, min(1.0, top_p))

        # Top K: >= 0
        if "top_k" in raw_params and raw_params["top_k"] is not None:
            top_k = int(raw_params["top_k"])
            normalized["top_k"] = max(0, top_k)

        # Min P: 0.0-1.0
        if "min_p" in raw_params and raw_params["min_p"] is not None:
            min_p = float(raw_params["min_p"])
            normalized["min_p"] = max(0.0, min(1.0, min_p))

        # Top A: 0.0-1.0
        if "top_a" in raw_params and raw_params["top_a"] is not None:
            top_a = float(raw_params["top_a"])
            normalized["top_a"] = max(0.0, min(1.0, top_a))

        # Frequency Penalty: -2.0-2.0
        if (
            "frequency_penalty" in raw_params
            and raw_params["frequency_penalty"] is not None
        ):
            freq_pen = float(raw_params["frequency_penalty"])
            normalized["frequency_penalty"] = max(-2.0, min(2.0, freq_pen))

        # Presence Penalty: -2.0-2.0
        if (
            "presence_penalty" in raw_params
            and raw_params["presence_penalty"] is not None
        ):
            pres_pen = float(raw_params["presence_penalty"])
            normalized["presence_penalty"] = max(-2.0, min(2.0, pres_pen))

        # Repetition Penalty: 0.0-2.0
        if (
            "repetition_penalty" in raw_params
            and raw_params["repetition_penalty"] is not None
        ):
            rep_pen = float(raw_params["repetition_penalty"])
            normalized["repetition_penalty"] = max(0.0, min(2.0, rep_pen))

        # Max Tokens: >= 1
        if "max_tokens" in raw_params and raw_params["max_tokens"] is not None:
            max_tokens = int(raw_params["max_tokens"])
            normalized["max_tokens"] = max(1, max_tokens)

        return normalized

    def validate(self, config: StandardizedConfig) -> tuple[bool, str]:
        """
        校验LLM配置。

        Args:
            config: 待校验的配置。

        Returns:
            (是否有效, 错误信息)
        """
        if config.task_type != "llm":
            return False, f"Task type must be 'llm', got '{config.task_type}'"

        if not config.model_id:
            return False, "Model ID is required"

        if not config.provider_id:
            return False, "Provider ID is required"

        return True, ""
