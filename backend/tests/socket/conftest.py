# -*- coding: utf-8 -*-
"""Socket 测试专用 conftest — 覆盖顶层 fixtures 避免与真实 uvicorn 服务器冲突。"""

import pytest


@pytest.fixture(autouse=True)
def _reset_icon_proxy():
    """No-op：socket 测试不需要图标代理（避免创建 httpx 客户端干扰事件循环）。"""
    yield


@pytest.fixture(scope="module")
def _test_app():
    """No-op：socket 测试启动自己的 FastAPI/uvicorn 服务器。"""
    return None
