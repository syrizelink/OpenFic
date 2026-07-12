import pytest

from app.macro.compiler import EntryInput, PromptChainCompiler


@pytest.mark.asyncio
async def test_compile_preserves_macro_text():
    compiler = PromptChainCompiler()
    entries = [
        EntryInput(
            role="system",
            content=(
                "{{getmem::chapter::latest}}\n"
                "{{getworld}}\n"
                "{{if::enabled}}保留内容{{endif}}"
            ),
            order_index=0,
            is_enabled=True,
        )
    ]

    result = await compiler.compile(entries)

    assert result.entries[0].content == entries[0].content
