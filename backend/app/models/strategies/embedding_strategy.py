# -*- coding: utf-8 -*-
"""
Embedding Strategy - Embedding模型策略。

处理Embedding模型的参数规范化和校验。
"""

from typing import Any

from app.models.strategies.base import BaseStrategy, StandardizedConfig


class EmbeddingStrategy(BaseStrategy):
    """Embedding模型策略，处理文本嵌入相关的参数。"""

    def normalize_parameters(self, raw_params: dict[str, Any]) -> dict[str, Any]:
        """
        规范化Embedding参数。

        Args:
            raw_params: 原始参数（可能包含dimensions等）。

        Returns:
            规范化后的参数字典。
        """
        normalized: dict[str, Any] = {}

        # Dimensions: >= 1
        if "dimensions" in raw_params and raw_params["dimensions"] is not None:
            dimensions = int(raw_params["dimensions"])
            normalized["dimensions"] = max(1, dimensions)

        return normalized

    def validate(self, config: StandardizedConfig) -> tuple[bool, str]:
        """
        校验Embedding配置。

        Args:
            config: 待校验的配置。

        Returns:
            (是否有效, 错误信息)
        """
        if config.task_type != "embedding":
            return False, f"Task type must be 'embedding', got '{config.task_type}'"

        if not config.model_id:
            return False, "Model ID is required"

        if not config.provider_id:
            return False, "Provider ID is required"

        # 校验dimensions
        if "dimensions" in config.parameters:
            dims = config.parameters["dimensions"]
            if dims < 1:
                return False, f"Dimensions must be >= 1, got {dims}"

        return True, ""
