# -*- coding: utf-8 -*-
"""
Macro Evaluator - 宏求值器。

负责遍历文本中的宏并求值替换。
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
    """宏求值器。"""

    def __init__(self, context: MacroContext | None = None):
        """
        初始化求值器。

        Args:
            context: 求值上下文。如果不提供，会创建一个空上下文。
        """
        self.context = context or MacroContext()

    def evaluate_text(self, text: str, ignore_macros: set[str] | None = None) -> str:
        """
        对文本中的所有宏求值并替换。

        Args:
            text: 源文本。
            ignore_macros: 忽略求值的宏名集合（保持原样）。

        Returns:
            替换后的文本。

        Raises:
            MacroEvaluateError: 求值错误。
        """
        ignore_macros = ignore_macros or set()

        # 首先处理非条件宏
        matches = MacroLexer.find_macros(text)
        if matches:
            current_text = text
            offset = 0

            for match in matches:
                adjusted_start = match.start + offset
                adjusted_end = match.end + offset

                try:
                    node = MacroParser.parse(match)

                    # 跳过 if/endif（稍后处理）
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
                    # 解析或求值失败，跳过该宏（保持原样）
                    continue

            text = current_text

        # 然后处理 if/endif 块。
        if "if" not in ignore_macros and "endif" not in ignore_macros:
            text = self._process_conditional_blocks(text)

        return text

    def _process_conditional_blocks(self, text: str) -> str:
        """
        处理 if/endif 条件块（支持嵌套）。

        Args:
            text: 源文本。

        Returns:
            处理后的文本。
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
        对单个宏节点求值。

        Args:
            node: 宏 AST 节点。

        Returns:
            求值结果。

        Raises:
            MacroEvaluateError: 求值错误。
        """
        return self._evaluate_node(node)

    def _evaluate_node(self, node: MacroNode) -> str:
        """内部求值方法。"""
        handler = HANDLER_MAP.get(node.name)
        if not handler:
            raise MacroEvaluateError(f"未知的宏: {node.name}", node)

        return handler.evaluate(node, self.context)

    def _apply_replacements(self, text: str, results: list[MacroResult]) -> str:
        """
        应用替换结果。

        从后向前替换以保持位置正确。

        Args:
            text: 源文本。
            results: 求值结果列表。

        Returns:
            替换后的文本。
        """
        sorted_results = sorted(results, key=lambda r: r.start, reverse=True)

        for result in sorted_results:
            text = text[: result.start] + result.value + text[result.end :]

        return text

    def get_all_macros(self, text: str) -> list[MacroNode]:
        """
        获取文本中所有有效的宏节点。

        Args:
            text: 源文本。

        Returns:
            宏节点列表。
        """
        return MacroParser.parse_all(text)
