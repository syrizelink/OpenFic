from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.macro.compiler import EntryInput, PromptChainCompiler


@pytest.mark.asyncio
async def test_compile_uses_chapter_context_when_chapter_id_provided():
    mock_session = AsyncMock()
    compiler = PromptChainCompiler(mock_session)
    entries = [
        EntryInput(
            role="system",
            content="{{getmem::chapter::latest}}",
            order_index=0,
            is_enabled=True,
        )
    ]

    with patch.object(
        compiler,
        "_load_chapter_context",
        AsyncMock(return_value=SimpleNamespace(latest_field="chapter text")),
    ) as mocked_load, patch.object(
        compiler,
        "_load_world_context",
        AsyncMock(return_value=None),
    ):
        result = await compiler.compile(entries, project_id="p1", chapter_id="c0")

    mocked_load.assert_awaited_once_with("p1", "c0")
    assert result.entries[0].content == "chapter text"
