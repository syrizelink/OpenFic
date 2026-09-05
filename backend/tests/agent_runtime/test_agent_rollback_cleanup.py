"""回滚时 checkpoint 清理降级逻辑的单测。

删除失败必须降级为告警而不是抛出：revision 层在此之前已提交，
重新抛出只会让前端重试并叠加 rollback revision。
"""

from unittest.mock import AsyncMock

import pytest

from app.api.routers.agent_runtime import _cleanup_checkpoints_until_boundary


@pytest.fixture
def delete_mocks(monkeypatch: pytest.MonkeyPatch) -> tuple[AsyncMock, AsyncMock]:
    after = AsyncMock(return_value=3)
    full = AsyncMock(return_value=5)
    monkeypatch.setattr(
        "app.api.routers.agent_runtime.delete_checkpoints_after_for_thread", after
    )
    monkeypatch.setattr(
        "app.api.routers.agent_runtime.delete_checkpoints_for_thread", full
    )
    return after, full


@pytest.mark.asyncio
async def test_cleanup_uses_boundary_delete_when_checkpoint_id_present(
    delete_mocks: tuple[AsyncMock, AsyncMock],
):
    after, full = delete_mocks

    ok = await _cleanup_checkpoints_until_boundary(
        "thread-1",
        "checkpoint-9",
        log_context={"session_id": "s-1"},
        failure_message="failed",
    )

    assert ok is True
    after.assert_awaited_once_with("thread-1", "checkpoint-9")
    full.assert_not_awaited()


@pytest.mark.asyncio
async def test_cleanup_uses_full_delete_without_checkpoint_id(
    delete_mocks: tuple[AsyncMock, AsyncMock],
):
    after, full = delete_mocks

    ok = await _cleanup_checkpoints_until_boundary(
        "thread-1",
        None,
        log_context={"session_id": "s-1"},
        failure_message="failed",
    )

    assert ok is True
    full.assert_awaited_once_with("thread-1")
    after.assert_not_awaited()


@pytest.mark.asyncio
async def test_cleanup_deletes_failure_to_false_instead_of_raising(
    delete_mocks: tuple[AsyncMock, AsyncMock],
):
    after, _full = delete_mocks
    after.side_effect = RuntimeError("database is locked")

    ok = await _cleanup_checkpoints_until_boundary(
        "thread-1",
        "checkpoint-9",
        log_context={"session_id": "s-1"},
        failure_message="failed",
    )

    assert ok is False
