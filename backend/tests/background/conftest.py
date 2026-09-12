# -*- coding: utf-8 -*-
"""conftest khusus uji background - menimpa fixture tingkat atas agar event loop tingkat modul tidak terganggu."""

import pytest


@pytest.fixture(autouse=True)
def _reset_icon_proxy():
    """No-op: uji background tidak memerlukan proxy ikon."""
    yield
