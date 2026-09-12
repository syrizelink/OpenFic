# -*- coding: utf-8 -*-
"""
HTTP Client Factory - factory klien HTTP.

Mengelola pembuatan klien HTTP secara terpusat agar pengaturan batas waktu,
retry, dan lainnya seragam.
"""

import httpx


class ClientFactory:
    """Factory klien HTTP, membuat klien HTTP dengan konfigurasi seragam."""

    DEFAULT_TIMEOUT = 30.0
    DEFAULT_FOLLOW_REDIRECTS = True

    @classmethod
    def create_client(
        cls,
        timeout: float = DEFAULT_TIMEOUT,
        follow_redirects: bool = DEFAULT_FOLLOW_REDIRECTS,
        **kwargs,
    ) -> httpx.AsyncClient:
        """
        Membuat klien HTTP asinkron.

        Args:
            timeout: batas waktu (detik).
            follow_redirects: apakah mengikuti redirect.
            **kwargs: parameter lain yang diteruskan ke httpx.AsyncClient.

        Returns:
            Instance AsyncClient yang sudah dikonfigurasi.
        """
        return httpx.AsyncClient(
            timeout=timeout, follow_redirects=follow_redirects, **kwargs
        )

    @classmethod
    def create_retry_client(
        cls, max_retries: int = 3, timeout: float = DEFAULT_TIMEOUT, **kwargs
    ) -> httpx.AsyncClient:
        """
        Membuat klien HTTP dengan konfigurasi retry.

        Args:
            max_retries: jumlah retry maksimum.
            timeout: batas waktu.
            **kwargs: parameter lain.

        Returns:
            Instance AsyncClient yang sudah dikonfigurasi retry.
        """
        transport = httpx.AsyncHTTPTransport(retries=max_retries)
        return httpx.AsyncClient(timeout=timeout, transport=transport, **kwargs)
