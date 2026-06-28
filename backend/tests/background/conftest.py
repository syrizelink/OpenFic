# -*- coding: utf-8 -*-
"""Background 测试专用 conftest — 覆盖顶层 fixtures 避免模块级事件循环干扰。"""

import pytest


@pytest.fixture(autouse=True)
def _reset_icon_proxy():
    """No-op：background 测试不需要图标代理。"""
    yield
