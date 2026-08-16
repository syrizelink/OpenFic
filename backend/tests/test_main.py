import asyncio

import pytest

import app.main as main


def test_get_server_bind_reads_uvicorn_command_line_options(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENFIC_SERVER_HOST", raising=False)
    monkeypatch.delenv("OPENFIC_SERVER_PORT", raising=False)
    monkeypatch.setattr(
        main.sys,
        "argv",
        ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8001"],
    )

    assert main._get_server_bind() == ("127.0.0.1", 8001)


def test_get_server_bind_prioritizes_openfic_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENFIC_SERVER_HOST", "0.0.0.0")
    monkeypatch.setenv("OPENFIC_SERVER_PORT", "9000")
    monkeypatch.setattr(
        main.sys,
        "argv",
        ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8001"],
    )

    assert main._get_server_bind() == ("0.0.0.0", 9000)


@pytest.mark.asyncio
async def test_lifespan_refreshes_catalog_in_background_and_cancels_on_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    refresh_started = asyncio.Event()
    refresh_cancelled = asyncio.Event()

    async def wait_for_refresh_completion(self) -> None:
        refresh_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            refresh_cancelled.set()
            raise

    async def do_nothing() -> None:
        return None

    async def reset_task_state() -> int:
        return 0

    class FakeCatalogService:
        refresh = wait_for_refresh_completion

    monkeypatch.setattr(main, "ModelProviderCatalogService", FakeCatalogService, raising=False)
    monkeypatch.setattr(main, "init_db", do_nothing)
    monkeypatch.setattr(main, "_reset_task_running_state", reset_task_state)
    monkeypatch.setattr(main, "_reset_interrupted_child_run_state", reset_task_state)
    monkeypatch.setattr(main, "_reset_active_revision_state", reset_task_state)
    monkeypatch.setattr(main, "_load_telemetry_enabled", do_nothing)
    monkeypatch.setattr(main, "_seed_builtin_models", do_nothing)
    monkeypatch.setattr(main, "init_checkpointer", do_nothing)
    monkeypatch.setattr(main, "_cleanup_unreachable_checkpoints", do_nothing)
    monkeypatch.setattr(main, "_cleanup_chapter_export_files", do_nothing)
    monkeypatch.setattr(main, "_cleanup_orphaned_agent_attachment_files", do_nothing)
    monkeypatch.setattr(main, "_cleanup_orphaned_task_data", do_nothing)
    monkeypatch.setattr(main, "_vacuum_main_database", do_nothing)
    monkeypatch.setattr(main, "load_audit_details_persistence", do_nothing)
    monkeypatch.setattr(main, "start_audit_queue", lambda: None)
    monkeypatch.setattr(main, "start_background_runtime", do_nothing)
    monkeypatch.setattr(main, "_print_startup_banner", lambda _: None)
    monkeypatch.setattr(main, "stop_background_runtime", do_nothing)
    monkeypatch.setattr(main, "stop_audit_queue", do_nothing)
    monkeypatch.setattr(main, "close_checkpointer", do_nothing)
    monkeypatch.setattr(main, "close_db", do_nothing)

    async with main.lifespan(main.fastapi_app):
        await asyncio.wait_for(refresh_started.wait(), timeout=0.1)

    assert refresh_cancelled.is_set()
