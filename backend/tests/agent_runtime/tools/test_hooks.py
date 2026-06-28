from unittest.mock import AsyncMock, patch
from types import SimpleNamespace

from app.agent_runtime.tools.base import HookContext
from app.agent_runtime.tools.hooks.auth import auth_hook


def _mock_db_session() -> SimpleNamespace:
    return SimpleNamespace(
        execute=AsyncMock(
            return_value=SimpleNamespace(scalar_one_or_none=lambda: None)
        )
    )


def _make_context(access_level: str = "write", tool_name: str = "test") -> HookContext:
    return HookContext(
        tool_name=tool_name,
        access_level=access_level,
        args={"some": "arg"},
        state={"session_id": "s1", "project_id": "p1"},
        config={"configurable": {"db_session": _mock_db_session()}},
    )


def _patch_permissions(permissions: dict[str, str]):
    return patch(
        "app.agent_runtime.tools.hooks.auth._read_user_permissions",
        new=AsyncMock(return_value=permissions),
    )


async def test_deny_blocks_readonly():
    with _patch_permissions({"ask_user": "deny"}):
        result = await auth_hook(_make_context(tool_name="ask_user", access_level="readonly"))
    assert result.proceed is False
    assert result.interrupt_payload is not None
    assert result.interrupt_payload["denied"] is True


async def test_deny_blocks_write():
    with _patch_permissions({"write_chapter": "deny"}):
        result = await auth_hook(_make_context(tool_name="write_chapter", access_level="write"))
    assert result.proceed is False
    assert result.interrupt_payload is not None
    assert result.interrupt_payload["denied"] is True


async def test_allow_allows_write():
    with _patch_permissions({"write_chapter": "allow"}):
        result = await auth_hook(_make_context(tool_name="write_chapter", access_level="write"))
    assert result.proceed is True
    assert result.interrupt_payload is None


async def test_allow_allows_readonly():
    with _patch_permissions({"read_chapter": "allow"}):
        result = await auth_hook(_make_context(tool_name="read_chapter", access_level="readonly"))
    assert result.proceed is True


async def test_ask_interrupts_write():
    with _patch_permissions({"write_chapter": "ask"}):
        result = await auth_hook(_make_context(tool_name="write_chapter", access_level="write"))
    assert result.proceed is False
    assert result.interrupt_payload is not None
    assert result.interrupt_payload["type"] == "tool_approval"
    assert result.interrupt_payload.get("denied") is not True


async def test_global_bypass_allows_write_without_approval():
    with (
        patch(
            "app.agent_runtime.tools.hooks.auth.setting_repo.get_by_key",
            new=AsyncMock(return_value=SimpleNamespace(value="true")),
        ),
        _patch_permissions({"write_chapter": "ask"}),
    ):
        result = await auth_hook(_make_context(tool_name="write_chapter", access_level="write"))
    assert result.proceed is True
    assert result.interrupt_payload is None


async def test_ask_interrupts_readonly():
    with _patch_permissions({"read_chapter": "ask"}):
        result = await auth_hook(_make_context(tool_name="read_chapter", access_level="readonly"))
    assert result.proceed is False
    assert result.interrupt_payload is not None
    assert result.interrupt_payload["type"] == "tool_approval"


async def test_fallback_to_default_metadata_allow():
    with _patch_permissions({}):
        result = await auth_hook(_make_context(tool_name="ask_user", access_level="readonly"))
    assert result.proceed is True


async def test_fallback_to_default_metadata_ask():
    with _patch_permissions({}):
        result = await auth_hook(_make_context(tool_name="write_chapter", access_level="write"))
    assert result.proceed is False
    assert result.interrupt_payload is not None


async def test_fallback_to_access_level_readonly():
    with _patch_permissions({}):
        result = await auth_hook(_make_context(tool_name="unregistered_readonly", access_level="readonly"))
    assert result.proceed is True


async def test_fallback_to_access_level_write():
    with _patch_permissions({}):
        result = await auth_hook(_make_context(tool_name="unknown_tool", access_level="write"))
    assert result.proceed is False
    assert result.interrupt_payload is not None
    assert result.interrupt_payload["type"] == "tool_approval"


async def test_args_included_in_payload():
    with _patch_permissions({"write_chapter": "ask"}):
        result = await auth_hook(_make_context(tool_name="write_chapter", access_level="write"))
    assert result.interrupt_payload["args"] == {"some": "arg"}


async def test_write_chapter_approval_payload_stays_permission_only():
    context = HookContext(
        tool_name="write_chapter",
        access_level="write",
        args={"title": "新章节", "content": "新内容"},
        state={"session_id": "s1", "project_id": "p1"},
        config={"configurable": {"db_session": _mock_db_session()}},
        tool_call_id="call-write-1",
    )
    with _patch_permissions({"write_chapter": "ask"}):
        result = await auth_hook(context)
    assert result.proceed is False
    assert result.interrupt_payload is not None
    assert result.interrupt_payload == {
        "type": "tool_approval",
        "tool_name": "write_chapter",
        "args": {"title": "新章节", "content": "新内容"},
    }
