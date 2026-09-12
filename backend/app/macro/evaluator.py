# -*- coding: utf-8 -*-
"""
Macro Evaluator - evaluator makro.

Bertugas menelusuri makro di dalam teks lalu mengevaluasi dan menggantinya.
"""

from app.macro.lexer import MacroLexer
from app.macro.parser import MacroParser
from app.macro.types import MacroContext, MacroNode, MacroResult
from app.macro.handlers.base import MacroHandler, MacroEvaluateError
from app.macro.handlers.mem_handler import GetListHandler, GetMemHandler, GetWorldHandler
from app.macro.handlers.conditional_handler import IfHandler, EndIfHandler


HANDLER_MAP: dict[str, MacroHandler] = {
    "getmem": GetMemHandler(),
    "getlist": GetListHandler(),
    "getworld": GetWorldHandler(),
    "if": IfHandler(),
    "endif": EndIfHandler(),
}


class MacroEvaluator:
    """Evaluator makro."""

    def __init__(self, context: MacroContext | None = None):
        """
        Menginisialisasi evaluator.

        Args:
            context: Konteks evaluasi. Jika tidak diberikan, konteks kosong akan dibuat.
        """
        self.context = context or MacroContext()

    def evaluate_text(self, text: str, ignore_macros: set[str] | None = None) -> str:
        """
        Mengevaluasi dan mengganti semua makro di dalam teks.

        Args:
            text: Teks sumber.
            ignore_macros: Himpunan nama makro yang tidak dievaluasi (dibiarkan apa adanya).

        Returns:
            Teks setelah penggantian.

        Raises:
            MacroEvaluateError: Kesalahan evaluasi.
        """
        ignore_macros = ignore_macros or set()

        # Tangani makro non-kondisional terlebih dahulu
        matches = MacroLexer.find_macros(text)
        if matches:
            current_text = text
            offset = 0

            for match in matches:
                adjusted_start = match.start + offset
                adjusted_end = match.end + offset

                try:
                    node = MacroParser.parse(match)

                    # Lewati if/endif (ditangani nanti)
                    if node.name in ("if", "endif"):
                        continue

                    if node.name in ignore_macros:
                        continue

                    value = self._evaluate_node(node)
                    current_text = (
                        current_text[:adjusted_start]
                        + value
                        + current_text[adjusted_end:]
                    )
                    offset += len(value) - (match.end - match.start)
                except Exception:
                    # Penguraian atau evaluasi gagal, lewati makro ini (biarkan apa adanya)
                    continue

            text = current_text

        # Lalu tangani blok if/endif.
        if "if" not in ignore_macros and "endif" not in ignore_macros:
            text = self._process_conditional_blocks(text)

        return text

    def _process_conditional_blocks(self, text: str) -> str:
        """
        Menangani blok kondisional if/endif (mendukung penyarangan).

        Args:
            text: Teks sumber.

        Returns:
            Teks setelah diproses.
        """
        max_iterations = 10
        iteration = 0

        while iteration < max_iterations:
            matches = MacroLexer.find_macros(text)
            if not matches:
                break

            if_positions = []
            endif_positions = []

            for match in matches:
                try:
                    node = MacroParser.parse(match)
                    if node.name == "if":
                        if_positions.append((match, node))
                    elif node.name == "endif":
                        endif_positions.append(match)
                except Exception:
                    continue

            if not if_positions or not endif_positions:
                break

            found_pair = False
            for i, (if_match, if_node) in enumerate(if_positions):
                for endif_match in endif_positions:
                    if endif_match.start > if_match.end:
                        has_nested = False
                        for j, (other_if_match, _) in enumerate(if_positions):
                            if (
                                j != i
                                and if_match.end
                                < other_if_match.start
                                < endif_match.start
                            ):
                                has_nested = True
                                break

                        if not has_nested:
                            found_pair = True
                            block_content = text[if_match.end : endif_match.start]

                            try:
                                if_handler = HANDLER_MAP.get("if")
                                if if_handler is None:
                                    text = (
                                        text[: if_match.start] + text[endif_match.end :]
                                    )
                                else:
                                    result = if_handler.evaluate(if_node, self.context)
                                    condition_met = result == "true"

                                    if condition_met:
                                        text = (
                                            text[: if_match.start]
                                            + block_content
                                            + text[endif_match.end :]
                                        )
                                    else:
                                        text = (
                                            text[: if_match.start]
                                            + text[endif_match.end :]
                                        )
                            except Exception:
                                text = text[: if_match.start] + text[endif_match.end :]

                            break

                if found_pair:
                    break

            if not found_pair:
                break

            iteration += 1

        return text

    def evaluate_node(self, node: MacroNode) -> str:
        """
        Mengevaluasi satu node makro.

        Args:
            node: Node AST makro.

        Returns:
            Hasil evaluasi.

        Raises:
            MacroEvaluateError: Kesalahan evaluasi.
        """
        return self._evaluate_node(node)

    def _evaluate_node(self, node: MacroNode) -> str:
        """Metode evaluasi internal."""
        handler = HANDLER_MAP.get(node.name)
        if not handler:
            raise MacroEvaluateError(f"Makro tidak dikenal: {node.name}", node)

        return handler.evaluate(node, self.context)

    def _apply_replacements(self, text: str, results: list[MacroResult]) -> str:
        """
        Menerapkan hasil penggantian.

        Penggantian dilakukan dari belakang ke depan agar posisinya tetap benar.

        Args:
            text: Teks sumber.
            results: Daftar hasil evaluasi.

        Returns:
            Teks setelah penggantian.
        """
        sorted_results = sorted(results, key=lambda r: r.start, reverse=True)

        for result in sorted_results:
            text = text[: result.start] + result.value + text[result.end :]

        return text

    def get_all_macros(self, text: str) -> list[MacroNode]:
        """
        Mengambil semua node makro yang valid di dalam teks.

        Args:
            text: Teks sumber.

        Returns:
            Daftar node makro.
        """
        return MacroParser.parse_all(text)
