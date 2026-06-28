from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_runtime_host_modules_do_not_import_old_agent_host() -> None:
    for relative_path in [
        "app/main.py",
        "app/api/routers/agent_runtime.py",
        "app/api/routers/settings.py",
    ]:
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        legacy_host = "agent"
        assert f"from app.{legacy_host}." not in source
        assert f"import app.{legacy_host}." not in source


def test_main_no_longer_mounts_ai_chat_router() -> None:
    source = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "ai_chat" not in source
