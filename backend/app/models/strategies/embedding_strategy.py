# -*- coding: utf-8 -*-
"""
Embedding Strategy - strategi model embedding.

Menangani normalisasi dan validasi parameter model embedding.
"""

from typing import Any

from app.models.strategies.base import BaseStrategy, StandardizedConfig


class EmbeddingStrategy(BaseStrategy):
    """Strategi model embedding, menangani parameter terkait embedding teks."""

    def normalize_parameters(self, raw_params: dict[str, Any]) -> dict[str, Any]:
        """
        Menormalkan parameter embedding.

        Args:
            raw_params: parameter asli (mungkin memuat dimensions, dll).

        Returns:
            Kamus parameter setelah dinormalkan.
        """
        normalized: dict[str, Any] = {}

        # Dimensions: >= 1
        if "dimensions" in raw_params and raw_params["dimensions"] is not None:
            dimensions = int(raw_params["dimensions"])
            normalized["dimensions"] = max(1, dimensions)

        return normalized

    def validate(self, config: StandardizedConfig) -> tuple[bool, str]:
        """
        Memvalidasi konfigurasi embedding.

        Args:
            config: konfigurasi yang akan divalidasi.

        Returns:
            (apakah valid, pesan kesalahan)
        """
        if config.task_type != "embedding":
            return False, f"Task type must be 'embedding', got '{config.task_type}'"

        if not config.model_id:
            return False, "Model ID is required"

        if not config.provider_id:
            return False, "Provider ID is required"

        # Validasi dimensions
        if "dimensions" in config.parameters:
            dims = config.parameters["dimensions"]
            if dims < 1:
                return False, f"Dimensions must be >= 1, got {dims}"

        return True, ""
