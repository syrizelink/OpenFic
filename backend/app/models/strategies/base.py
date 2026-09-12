# -*- coding: utf-8 -*-
"""
Base Strategy - kelas dasar strategi.

Strategy bertugas memilih model, menormalkan parameter, dan validasi;
tidak melakukan pemanggilan HTTP.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class StandardizedConfig:
    """Struktur konfigurasi model yang terpadu."""

    model_id: str
    task_type: str
    provider_type: str
    provider_id: str
    parameters: dict[str, Any]

    def __post_init__(self):
        """Memvalidasi keabsahan dasar konfigurasi."""
        if self.task_type not in ("llm", "embedding", "rerank"):
            raise ValueError(f"Invalid task_type: {self.task_type}")


class BaseStrategy(ABC):
    """Kelas dasar strategi, mendefinisikan tanggung jawab utama strategi."""

    @abstractmethod
    def normalize_parameters(self, raw_params: dict[str, Any]) -> dict[str, Any]:
        """
        Menormalkan parameter.

        Args:
            raw_params: kamus parameter asli.

        Returns:
            Kamus parameter setelah dinormalkan.
        """
        pass

    @abstractmethod
    def validate(self, config: StandardizedConfig) -> tuple[bool, str]:
        """
        Memvalidasi konfigurasi.

        Args:
            config: konfigurasi yang akan divalidasi.

        Returns:
            (apakah valid, pesan kesalahan)
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
        Membuat konfigurasi terstandardisasi.

        Args:
            model_id: ID model.
            task_type: jenis tugas.
            provider_type: jenis penyedia.
            provider_id: ID penyedia.
            raw_params: parameter asli.

        Returns:
            Konfigurasi model terstandardisasi.

        Raises:
            ValueError: jika parameter tidak valid.
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
