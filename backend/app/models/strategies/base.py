# -*- coding: utf-8 -*-
"""
Base Strategy - 策略基类。

Strategy负责模型选择、参数规范化和校验，不做HTTP调用。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class StandardizedConfig:
    """统一的模型配置结构。"""

    model_id: str
    task_type: str
    provider_type: str
    provider_id: str
    parameters: dict[str, Any]

    def __post_init__(self):
        """验证配置的基本有效性。"""
        if self.task_type not in ("llm", "embedding", "rerank"):
            raise ValueError(f"Invalid task_type: {self.task_type}")


class BaseStrategy(ABC):
    """策略基类，定义策略的核心职责。"""

    @abstractmethod
    def normalize_parameters(self, raw_params: dict[str, Any]) -> dict[str, Any]:
        """
        规范化参数。

        Args:
            raw_params: 原始参数字典。

        Returns:
            规范化后的参数字典。
        """
        pass

    @abstractmethod
    def validate(self, config: StandardizedConfig) -> tuple[bool, str]:
        """
        校验配置。

        Args:
            config: 待校验的配置。

        Returns:
            (是否有效, 错误信息)
        """
        pass

    def create_config(
        self,
        model_id: str,
        task_type: str,
        provider_type: str,
        provider_id: str,
        raw_params: dict[str, Any],
    ) -> StandardizedConfig:
        """
        创建标准化配置。

        Args:
            model_id: 模型ID。
            task_type: 任务类型。
            provider_type: 提供商类型。
            provider_id: 提供商ID。
            raw_params: 原始参数。

        Returns:
            标准化的模型配置。

        Raises:
            ValueError: 如果参数无效。
        """
        normalized_params = self.normalize_parameters(raw_params)
        config = StandardizedConfig(
            model_id=model_id,
            task_type=task_type,
            provider_type=provider_type,
            provider_id=provider_id,
            parameters=normalized_params,
        )

        is_valid, error_msg = self.validate(config)
        if not is_valid:
            raise ValueError(f"Invalid configuration: {error_msg}")

        return config
