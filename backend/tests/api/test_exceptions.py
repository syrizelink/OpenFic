# -*- coding: utf-8 -*-
"""全局异常处理器测试。"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.exceptions import register_exception_handlers


@pytest.mark.asyncio
async def test_unhandled_exception_returns_generic_500() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("secret internal detail")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal Server Error"}
