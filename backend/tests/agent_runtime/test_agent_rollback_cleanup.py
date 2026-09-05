"""回滚时 checkpoint 清理的失败语义测试。

删除失败必须抛 503 引导用户重做回滚：revision 层在此之前已提交，
重做是幂等的（包括子代理清理边界重算），静默降级会让数据层与
会话状态层无声分叉且没有修复入口。
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

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

    await _cleanup_checkpoints_until_boundary(
        "thread-1",
        "checkpoint-9",
        log_context={"session_id": "s-1"},
        failure_message="failed",
    )

    after.assert_awaited_once_with("thread-1", "checkpoint-9", retry_on_busy=True)
    full.assert_not_awaited()


@pytest.mark.asyncio
async def test_cleanup_uses_full_delete_without_checkpoint_id(
    delete_mocks: tuple[AsyncMock, AsyncMock],
):
    after, full = delete_mocks

    await _cleanup_checkpoints_until_boundary(
        "thread-1",
        None,
        log_context={"session_id": "s-1"},
        failure_message="failed",
    )

    full.assert_awaited_once_with("thread-1", retry_on_busy=True)
    after.assert_not_awaited()


@pytest.mark.asyncio
async def test_cleanup_raises_503_when_delete_finally_fails(
    delete_mocks: tuple[AsyncMock, AsyncMock],
):
    after, _full = delete_mocks
    after.side_effect = RuntimeError("database is locked")

    with pytest.raises(HTTPException) as excinfo:
        await _cleanup_checkpoints_until_boundary(
            "thread-1",
            "checkpoint-9",
            log_context={"session_id": "s-1"},
            failure_message="failed",
        )

    assert excinfo.value.status_code == 503
