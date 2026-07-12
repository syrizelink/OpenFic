# -*- coding: utf-8 -*-
"""
Prompt Chain Compiler - 提示词链编译器。

负责编译 prompt chain，保留条目原始内容。
"""

from dataclasses import dataclass


@dataclass
class CompiledEntry:
    """
    编译后的条目。

    Attributes:
        role: 角色类型。
        content: 编译后的内容。
        token_count: Token 计数（编译后）。
    """

    role: str
    content: str
    token_count: int


@dataclass
class CompileResult:
    """
    编译结果。

    Attributes:
        entries: 编译后的条目列表。
        total_tokens: 总 Token 数。
    """

    entries: list[CompiledEntry]
    total_tokens: int


@dataclass
class EntryInput:
    """
    编译输入条目。

    Attributes:
        role: 角色类型。
        content: 原始内容。
        order_index: 排序索引。
        is_enabled: 是否启用。
    """

    role: str
    content: str
    order_index: int
    is_enabled: bool


class PromptChainCompiler:
    """提示词链编译器。"""

    async def compile(
        self,
        entries: list[EntryInput],
    ) -> CompileResult:
        """
        编译提示词链。

        Args:
            entries: 条目列表（按 order_index 排序）。
        Returns:
            编译结果。
        """
        sorted_entries = sorted(entries, key=lambda e: e.order_index)
        enabled_entries = [e for e in sorted_entries if e.is_enabled]

        compiled_entries: list[CompiledEntry] = []
        total_tokens = 0

        for entry in enabled_entries:
            token_count = self._estimate_tokens(entry.content)
            total_tokens += token_count

            compiled_entries.append(
                CompiledEntry(
                    role=entry.role,
                    content=entry.content,
                    token_count=token_count,
                )
            )

        return CompileResult(
            entries=compiled_entries,
            total_tokens=total_tokens,
        )

    def _estimate_tokens(self, text: str) -> int:
        """估算 token 数量。"""
        return len(text) // 2
