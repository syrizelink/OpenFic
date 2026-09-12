# -*- coding: utf-8 -*-
"""conftest khusus uji socket - menimpa fixture tingkat atas agar tidak berbenturan dengan server uvicorn nyata."""

import pytest


@pytest.fixture(autouse=True)
def _reset_icon_proxy():
    """No-op: uji socket tidak memerlukan proxy ikon (menghindari pembuatan klien httpx yang mengganggu event loop)."""
    yield


@pytest.fixture(scope="module")
def _test_app():
    """No-op: uji socket menjalankan server FastAPI/uvicorn sendiri."""
    return None
