import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

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


@pytest.mark.asyncio
async def test_postgresql_startup_skips_sqlite_checkpoint_maintenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def record(name: str) -> int:
        calls.append(name)
        return 0

    monkeypatch.setattr(main.app_settings, "database_backend", "postgresql")
    monkeypatch.setattr(main, "logger", Mock())
    maintenance_state = SimpleNamespace(
        updates=[],
        start=Mock(),
        update=lambda **values: maintenance_state.updates.append(values),
        complete=Mock(),
        fail=Mock(),
    )
    monkeypatch.setattr(main, "maintenance_state", maintenance_state)

    sqlite_checkpoint_functions = (
        "needs_incremental_auto_vacuum_migration",
        "migrate_checkpoint_database_to_incremental",
        "checkpoint_free_page_bytes",
        "full_vacuum_checkpoint_database",
    )
    for name in sqlite_checkpoint_functions:
        function = AsyncMock()
        if name == "needs_incremental_auto_vacuum_migration":
            function.return_value = False
        elif name == "checkpoint_free_page_bytes":
            function.return_value = (0, 1)
        else:
            function.return_value = False
        monkeypatch.setattr(main, name, function)

    monkeypatch.setattr(main, "close_checkpointer", AsyncMock())
    monkeypatch.setattr(main, "init_checkpointer", AsyncMock(side_effect=lambda: calls.append("init_checkpointer")))
    monkeypatch.setattr(main, "_cleanup_unreachable_checkpoints", AsyncMock(side_effect=lambda: calls.append("checkpoint_cleanup")))
    for name in (
        "_cleanup_chapter_export_files",
        "_cleanup_orphaned_agent_attachment_files",
        "_cleanup_orphaned_task_data",
        "_cleanup_orphaned_revision_data",
        "_backfill_revision_content",
        "_vacuum_main_database",
    ):
        monkeypatch.setattr(main, name, AsyncMock(side_effect=lambda name=name: calls.append(name)))
    monkeypatch.setattr(main, "start_background_runtime", AsyncMock())

    await main._run_startup_maintenance()

    assert "init_checkpointer" in calls
    assert "_cleanup_orphaned_revision_data" in calls
    assert "_backfill_revision_content" in calls
    assert "_vacuum_main_database" in calls
    assert "checkpoint_cleanup" not in calls
    for name in sqlite_checkpoint_functions:
        assert not getattr(main, name).await_args_list
    assert all(update.get("phase") not in {"migrating", "vacuuming"} for update in maintenance_state.updates)
    assert any(
        "backend=postgresql" in " ".join(map(str, call.args))
        for call in main.logger.info.call_args_list
    )


@pytest.mark.asyncio
async def test_sqlite_startup_keeps_checkpoint_maintenance_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main.app_settings, "database_backend", "sqlite")
    monkeypatch.setattr(main, "logger", Mock())
    monkeypatch.setattr(main, "maintenance_state", SimpleNamespace(
        start=Mock(),
        update=Mock(),
        complete=Mock(),
        fail=Mock(),
    ))
    needs_migration = AsyncMock(return_value=False)
    free_pages = AsyncMock(return_value=(0, 1))
    for name, function in (
        ("needs_incremental_auto_vacuum_migration", needs_migration),
        ("checkpoint_free_page_bytes", free_pages),
    ):
        monkeypatch.setattr(main, name, function)
    monkeypatch.setattr(main, "close_checkpointer", AsyncMock())
    monkeypatch.setattr(main, "init_checkpointer", AsyncMock())
    monkeypatch.setattr(main, "_cleanup_unreachable_checkpoints", AsyncMock())
    for name in (
        "_cleanup_chapter_export_files",
        "_cleanup_orphaned_agent_attachment_files",
        "_cleanup_orphaned_task_data",
        "_cleanup_orphaned_revision_data",
        "_backfill_revision_content",
        "_vacuum_main_database",
    ):
        monkeypatch.setattr(main, name, AsyncMock())
    monkeypatch.setattr(main, "start_background_runtime", AsyncMock())

    await main._run_startup_maintenance()

    needs_migration.assert_awaited_once()
    free_pages.assert_awaited_once()
