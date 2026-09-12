# -*- coding: utf-8 -*-
"""
Prompt Chain Compiler - kompilator rantai prompt.

Bertugas mengompilasi prompt chain dengan mempertahankan isi asli setiap entri.
"""

from dataclasses import dataclass


@dataclass
class CompiledEntry:
    """
    Entri hasil kompilasi.

    Attributes:
        role: Tipe peran.
        content: Isi hasil kompilasi.
        token_count: Jumlah Token (setelah kompilasi).
    """

    role: str
    content: str
    token_count: int


@dataclass
class CompileResult:
    """
    Hasil kompilasi.

    Attributes:
        entries: Daftar entri hasil kompilasi.
        total_tokens: Total jumlah Token.
    """

    entries: list[CompiledEntry]
    total_tokens: int


@dataclass
class EntryInput:
    """
    Entri masukan kompilasi.

    Attributes:
        role: Tipe peran.
        content: Isi asli.
        order_index: Indeks urutan.
        is_enabled: Apakah aktif.
    """

    role: str
    content: str
    order_index: int
    is_enabled: bool


class PromptChainCompiler:
    """Kompilator rantai prompt."""

    async def compile(
        self,
        entries: list[EntryInput],
    ) -> CompileResult:
        """
        Mengompilasi rantai prompt.

        Args:
            entries: Daftar entri (diurutkan berdasarkan order_index).
        Returns:
            Hasil kompilasi.
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
        """Memperkirakan jumlah token."""
        return len(text) // 2
