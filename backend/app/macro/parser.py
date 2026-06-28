# -*- coding: utf-8 -*-
"""
Macro Parser - 宏语法解析器。

负责将宏体解析为 AST 节点。
"""

from app.macro.lexer import MacroLexer, MacroMatch
from app.macro.registry import is_valid_macro
from app.macro.types import MacroNode


class MacroParseError(Exception):
    """宏解析错误。"""

    def __init__(self, message: str, raw: str):
        super().__init__(message)
        self.raw = raw


class MacroParser:
    """宏语法解析器。"""

    @classmethod
    def parse(cls, match: MacroMatch) -> MacroNode:
        """
        解析宏匹配为 AST 节点。

        Args:
            match: 宏匹配结果。

        Returns:
            宏 AST 节点。

        Raises:
            MacroParseError: 解析错误。
        """
        body = match.body

        parts = body.split("::", 1)
        name = parts[0].strip()

        if not name:
            raise MacroParseError("宏名不能为空", match.raw)

        if not is_valid_macro(name):
            raise MacroParseError(f"未知的宏名: {name}", match.raw)

        args_str = parts[1] if len(parts) > 1 else ""

        try:
            args = MacroLexer.tokenize_args(args_str)
        except ValueError as e:
            raise MacroParseError(str(e), match.raw)

        if name == "getmem":
            from app.macro.handlers.mem_handler import GetMemHandler

            try:
                GetMemHandler().validate(
                    MacroNode(
                        name=name,
                        args=args,
                        raw=match.raw,
                        start=match.start,
                        end=match.end,
                    )
                )
            except Exception as exc:
                raise MacroParseError(str(exc), match.raw) from exc

        if name == "getlist":
            from app.macro.handlers.mem_handler import GetListHandler

            try:
                GetListHandler().validate(
                    MacroNode(
                        name=name,
                        args=args,
                        raw=match.raw,
                        start=match.start,
                        end=match.end,
                    )
                )
            except Exception as exc:
                raise MacroParseError(str(exc), match.raw) from exc

        if name == "getworld":
            from app.macro.handlers.mem_handler import GetWorldHandler

            try:
                GetWorldHandler().validate(
                    MacroNode(
                        name=name,
                        args=args,
                        raw=match.raw,
                        start=match.start,
                        end=match.end,
                    )
                )
            except Exception as exc:
                raise MacroParseError(str(exc), match.raw) from exc

        return MacroNode(
            name=name,
            args=args,
            raw=match.raw,
            start=match.start,
            end=match.end,
        )

    @classmethod
    def parse_all(cls, text: str) -> list[MacroNode]:
        """
        解析文本中所有有效的宏。

        Args:
            text: 源文本。

        Returns:
            宏 AST 节点列表（仅包含解析成功的）。
        """
        matches = MacroLexer.find_macros(text)
        nodes = []

        for match in matches:
            try:
                node = cls.parse(match)
                nodes.append(node)
            except MacroParseError:
                pass

        return nodes

    @classmethod
    def try_parse(cls, match: MacroMatch) -> MacroNode | None:
        """
        尝试解析宏匹配，失败返回 None。

        Args:
            match: 宏匹配结果。

        Returns:
            宏 AST 节点，或 None（解析失败）。
        """
        try:
            return cls.parse(match)
        except MacroParseError:
            return None
