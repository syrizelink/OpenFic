# -*- coding: utf-8 -*-
"""PostHog 错误遥测模块单元测试。"""

import logging
from types import SimpleNamespace

from app import telemetry


def test_parse_telemetry_enabled_defaults_true() -> None:
    assert telemetry.parse_telemetry_enabled(None) is True
    assert telemetry.parse_telemetry_enabled("") is True
    assert telemetry.parse_telemetry_enabled("true") is True
    assert telemetry.parse_telemetry_enabled("false") is False
    assert telemetry.parse_telemetry_enabled("not-json") is True


def test_capture_exception_noop_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr(telemetry, "_enabled", False)
    monkeypatch.setattr(telemetry, "_client", None)
    telemetry.capture_exception(RuntimeError("boom"))


def test_capture_exception_calls_client(monkeypatch) -> None:
    calls: list[tuple] = []

    class _FakeClient:
        def capture_exception(self, exc, *, distinct_id=None, properties=None):
            calls.append((exc, distinct_id, properties))

    monkeypatch.setattr(telemetry, "_enabled", True)
    monkeypatch.setattr(telemetry, "_client", _FakeClient())
    err = RuntimeError("boom")
    telemetry.capture_exception(err, properties={"k": "v"})

    assert len(calls) == 1
    assert calls[0][0] is err
    assert calls[0][1]
    assert calls[0][2]["k"] == "v"
    assert calls[0][2]["source"] == "backend"


def _message(
    *,
    level_no: int,
    exception,
    name: str = "app.test",
    message: str = "failed",
    extra: dict | None = None,
) -> SimpleNamespace:
    record = {
        "level": SimpleNamespace(no=level_no),
        "exception": exception,
        "name": name,
        "message": message,
        "extra": extra or {},
    }
    return SimpleNamespace(record=record)


def test_error_sink_captures_error_with_exception(monkeypatch) -> None:
    captured: list[tuple] = []

    def fake_capture(exc, *, properties=None):
        captured.append((exc, properties))

    monkeypatch.setattr(telemetry, "_enabled", True)
    monkeypatch.setattr(telemetry, "_client", object())
    monkeypatch.setattr(telemetry, "capture_exception", fake_capture)

    err = RuntimeError("boom")
    telemetry._error_sink(
        _message(
            level_no=logging.ERROR,
            exception=(RuntimeError, err, None),
            extra={"request_method": "GET", "request_path": "/api/x"},
        )
    )

    assert len(captured) == 1
    assert captured[0][0] is err
    assert captured[0][1]["request_method"] == "GET"
    assert captured[0][1]["request_path"] == "/api/x"
    assert captured[0][1]["source"] == "backend"


def test_error_sink_skips_non_error_or_posthog(monkeypatch) -> None:
    captured: list = []

    def fake_capture(exc, *, properties=None):
        captured.append((exc, properties))

    monkeypatch.setattr(telemetry, "_enabled", True)
    monkeypatch.setattr(telemetry, "_client", object())
    monkeypatch.setattr(telemetry, "capture_exception", fake_capture)

    telemetry._error_sink(
        _message(level_no=logging.WARNING, exception=(RuntimeError, RuntimeError("x"), None))
    )
    telemetry._error_sink(_message(level_no=logging.ERROR, exception=None))
    telemetry._error_sink(
        _message(
            level_no=logging.ERROR,
            exception=(RuntimeError, RuntimeError("x"), None),
            name="posthog.client",
        )
    )

    assert captured == []
