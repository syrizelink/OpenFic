# -*- coding: utf-8 -*-
"""
Base Adapter - kelas dasar adapter.

Setiap Provider memiliki satu Adapter yang bertugas mengekspos daftar model
untuk berbagai jenis tugas.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping

import httpx


class BaseAdapter(ABC):
    """
    Kelas dasar Adapter, mendefinisikan antarmuka konversi protokol Provider.

    Setiap Adapter konkret bertugas:
    1. Mengambil daftar model LLM yang didukung Provider tersebut
    2. Mengambil daftar model embedding yang didukung Provider tersebut
    3. Mengambil daftar model rerank yang didukung Provider tersebut
    """

    @property
    @abstractmethod
    def provider_type(self) -> str:
        """Mengembalikan identifier jenis provider untuk Adapter ini."""
        pass

    @abstractmethod
    async def get_llm_models(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> list[dict[str, str]]:
        """
        Mengambil daftar model LLM.

        Args:
            client: klien HTTP.
            base_url: URL dasar API Provider.
            api_key: API Key (teks polos).

        Returns:
            Daftar model, setiap elemen berupa {"id": "model-id", "name": "Model Name"}.
        """
        pass

    @abstractmethod
    async def get_embedding_models(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> list[dict[str, str]]:
        """
        Mengambil daftar model embedding.

        Args:
            client: klien HTTP.
            base_url: URL dasar API Provider.
            api_key: API Key (teks polos).

        Returns:
            Daftar model, setiap elemen berupa {"id": "model-id", "name": "Model Name"}.
        """
        pass

    async def get_rerank_models(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        api_key: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> list[dict[str, str]]:
        """
        Mengambil daftar model rerank.

        Secara default kembali ke daftar model LLM, cocok untuk provider yang hanya
        dapat menampilkan `/models` umum.
        """
        return await self.get_llm_models(client, base_url, api_key, headers=headers)

    def supports_llm(self) -> bool:
        """Memeriksa apakah Adapter ini mendukung model LLM. Default: didukung."""
        return True

    def supports_embedding(self) -> bool:
        """Memeriksa apakah Adapter ini mendukung model embedding. Default: didukung."""
        return True

    def supports_rerank(self) -> bool:
        """Memeriksa apakah Adapter ini mendukung model rerank. Default: tidak didukung."""
        return False

    # ========================
    # Metode utilitas
    # ========================

    def _build_auth_header(
        self,
        api_key: str,
        custom_headers: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        """Membangun header autentikasi Bearer."""
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        headers.update(custom_headers or {})
        return headers

    def _normalize_url(self, url: str) -> str:
        """Menormalkan URL, menghapus garis miring di akhir."""
        return url.rstrip("/")
