# -*- coding: utf-8 -*-
"""
HTTP Client Factory - HTTP客户端工厂。

集中管理HTTP客户端创建，便于配置统一的超时、重试等设置。
"""

import httpx


class ClientFactory:
    """HTTP客户端工厂，创建配置统一的HTTP客户端。"""

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
        创建异步HTTP客户端。

        Args:
            timeout: 超时时间（秒）。
            follow_redirects: 是否跟随重定向。
            **kwargs: 传递给httpx.AsyncClient的其他参数。

        Returns:
            配置好的AsyncClient实例。
        """
        return httpx.AsyncClient(
            timeout=timeout, follow_redirects=follow_redirects, **kwargs
        )

    @classmethod
    def create_retry_client(
        cls, max_retries: int = 3, timeout: float = DEFAULT_TIMEOUT, **kwargs
    ) -> httpx.AsyncClient:
        """
        创建带重试配置的HTTP客户端。

        Args:
            max_retries: 最大重试次数。
            timeout: 超时时间。
            **kwargs: 其他参数。

        Returns:
            配置了重试的AsyncClient实例。
        """
        transport = httpx.AsyncHTTPTransport(retries=max_retries)
        return httpx.AsyncClient(timeout=timeout, transport=transport, **kwargs)
