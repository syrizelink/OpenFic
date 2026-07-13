from types import SimpleNamespace
from unittest.mock import patch, AsyncMock
import pytest

from app.agent_runtime.context.parts.system_prompt import build_system_prompt
from app.macro.compiler import CompileResult, CompiledEntry


@pytest.mark.asyncio
async def test_system_prompt_compiles_and_preserves_entry_roles(make_state, mock_session):
    state = make_state(project_id="p1")
    version = SimpleNamespace(
        version=SimpleNamespace(id="v1"),
        entries=[
            SimpleNamespace(role="system", content="角色：作家", order_index=0, is_enabled=True),
            SimpleNamespace(role="user", content="先给出章节目标", order_index=1, is_enabled=True),
            SimpleNamespace(role="assistant", content="已理解目标", order_index=2, is_enabled=True),
        ],
    )
    compile_result = CompileResult(
        entries=[
            CompiledEntry(role="system", content="角色：作家", token_count=4),
            CompiledEntry(role="user", content="先给出章节目标", token_count=5),
            CompiledEntry(role="assistant", content="已理解目标", token_count=5),
        ],
        total_tokens=14,
    )

    with patch(
        "app.agent_runtime.context.parts.system_prompt.prompt_chain_service.get_latest_version_with_entries_or_default",
        AsyncMock(return_value=version),
    ), patch(
        "app.agent_runtime.context.parts.system_prompt.PromptChainCompiler"
    ) as MockCompiler:
        instance = MockCompiler.return_value
        instance.compile = AsyncMock(return_value=compile_result)
        messages = await build_system_prompt(state, "writer", mock_session)

    instance.compile.assert_awaited_once()
    assert "chapter_order" not in instance.compile.await_args.kwargs
    assert messages is not None
    assert [message.role for message in messages] == ["system", "user", "assistant"]
    assert [message.content for message in messages] == ["角色：作家", "先给出章节目标", "已理解目标"]
    assert all(message.metadata == {"part": "system_prompt"} for message in messages)


@pytest.mark.asyncio
async def test_system_prompt_loads_agent_prompt_chain_key(make_state, mock_session):
    state = make_state()
    version = SimpleNamespace(version=SimpleNamespace(id="v1"), entries=[])

    with patch(
        "app.agent_runtime.context.parts.system_prompt.prompt_chain_service.get_latest_version_with_entries_or_default",
        AsyncMock(return_value=version),
    ) as mocked_get:
        await build_system_prompt(state, "explorer", mock_session)

    mocked_get.assert_awaited_once_with(
        mock_session,
        prompt_id="builtin-agent--explorer",
    )


@pytest.mark.asyncio
async def test_system_prompt_skips_disabled_entries(make_state, mock_session):
    state = make_state()
    version = SimpleNamespace(
        version=SimpleNamespace(id="v1"),
        entries=[
            SimpleNamespace(role="system", content="A", order_index=0, is_enabled=True),
            SimpleNamespace(role="system", content="B", order_index=1, is_enabled=False),
        ],
    )
    captured_entries: list = []

    async def _capture(entries, **kwargs):
        captured_entries.extend(entries)
        return CompileResult(
            entries=[CompiledEntry(role="system", content=e.content, token_count=1) for e in entries],
            total_tokens=2,
        )

    with patch(
        "app.agent_runtime.context.parts.system_prompt.prompt_chain_service.get_latest_version_with_entries_or_default",
        AsyncMock(return_value=version),
    ), patch(
        "app.agent_runtime.context.parts.system_prompt.PromptChainCompiler"
    ) as MockCompiler:
        instance = MockCompiler.return_value
        instance.compile = AsyncMock(side_effect=_capture)
        await build_system_prompt(state, "writer", mock_session)

    assert all(e.is_enabled for e in captured_entries)


@pytest.mark.asyncio
async def test_system_prompt_compiler_failure_raises(make_state, mock_session):
    from app.agent_runtime.context.errors import ContextBuildError
    state = make_state()
    version = SimpleNamespace(
        version=SimpleNamespace(id="v1"),
        entries=[
            SimpleNamespace(role="system", content="A", order_index=0, is_enabled=True),
        ],
    )
    with patch(
        "app.agent_runtime.context.parts.system_prompt.prompt_chain_service.get_latest_version_with_entries_or_default",
        AsyncMock(return_value=version),
    ), patch(
        "app.agent_runtime.context.parts.system_prompt.PromptChainCompiler"
    ) as MockCompiler:
        instance = MockCompiler.return_value
        instance.compile = AsyncMock(side_effect=RuntimeError("boom"))
        with pytest.raises(ContextBuildError) as exc_info:
            await build_system_prompt(state, "writer", mock_session)
    assert exc_info.value.part == "system_prompt"
