# -*- coding: utf-8 -*-
"""
Macro Lexer - 宏词法分析器。

负责识别文本中的宏表达式和解析宏参数。
"""

import re
from dataclasses import dataclass

from app.macro.types import MacroToken, TokenType


@dataclass
class MacroMatch:
    """
    宏匹配结果。

    Attributes:
        body: 宏体（不含 {{ }}）。
        raw: 原始文本（含 {{ }}）。
        start: 在源文本中的起始位置。
        end: 在源文本中的结束位置。
    """

    body: str
    raw: str
    start: int
    end: int


class MacroLexer:
    """宏词法分析器。"""

    MACRO_PATTERN = re.compile(r"\{\{([^{}]+)\}\}")
    SEPARATOR = "::"

    @classmethod
    def find_macros(cls, text: str) -> list[MacroMatch]:
        """
        在文本中查找所有宏表达式。

        Args:
            text: 源文本。

        Returns:
            宏匹配列表。
        """
        matches = []
        for m in cls.MACRO_PATTERN.finditer(text):
            body = m.group(1).strip()
            if body and "\n" not in body:
                matches.append(
                    MacroMatch(
                        body=body,
                        raw=m.group(0),
                        start=m.start(),
                        end=m.end(),
                    )
                )
        return matches

    @classmethod
    def tokenize_args(cls, args_str: str) -> list[MacroToken]:
        """
        将参数字符串解析为 Token 列表。

        Args:
            args_str: 参数字符串（如 "var_name::\"value\""）。

        Returns:
            Token 列表。

        Raises:
            ValueError: 参数格式错误。
        """
        if not args_str:
            return []

        tokens = []
        parts = cls._split_args(args_str)

        for part in parts:
            token = cls._parse_token(part)
            tokens.append(token)

        return tokens

    @classmethod
    def _split_args(cls, args_str: str) -> list[str]:
        """
        按 :: 分隔参数，但需考虑字符串内的 ::。

        Args:
            args_str: 参数字符串。

        Returns:
            分割后的参数列表。
        """
        parts = []
        current = ""
        in_string = False
        i = 0

        while i < len(args_str):
            char = args_str[i]

            if char == '"' and (i == 0 or args_str[i - 1] != "\\"):
                in_string = not in_string
                current += char
            elif not in_string and args_str[i : i + 2] == cls.SEPARATOR:
                if current:
                    parts.append(current.strip())
                current = ""
                i += 1
            else:
                current += char

            i += 1

        if current:
            parts.append(current.strip())

        return parts

    @classmethod
    def _parse_token(cls, part: str) -> MacroToken:
        """
        解析单个参数为 Token。

        Args:
            part: 参数字符串。

        Returns:
            解析后的 Token。

        Raises:
            ValueError: 参数格式错误。
        """
        part = part.strip()

        if part.startswith('"') and part.endswith('"'):
            return cls._parse_string(part)

        if part.startswith("list(") and part.endswith(")"):
            return cls._parse_list(part)

        if part in ("true", "false"):
            return cls._parse_boolean(part)

        if "-" in part and not part.startswith("-"):
            return cls._parse_range(part)

        if cls._is_number(part):
            return cls._parse_number(part)

        if cls._is_identifier(part):
            return MacroToken(type=TokenType.IDENTIFIER, value=part, raw=part)

        raise ValueError(f"无法解析参数: {part}")

    @classmethod
    def _parse_string(cls, part: str) -> MacroToken:
        """解析字符串字面量。"""
        content = part[1:-1]
        unescaped = content.replace('\\"', '"')
        return MacroToken(type=TokenType.STRING, value=unescaped, raw=part)

    @classmethod
    def _parse_list(cls, part: str) -> MacroToken:
        """解析列表。"""
        content = part[5:-1]
        if not content:
            raise ValueError("列表不能为空")

        items = [item.strip() for item in content.split(",")]
        if any(not item for item in items):
            raise ValueError("列表项不能为空")

        return MacroToken(type=TokenType.LIST, value=items, raw=part)

    @classmethod
    def _parse_range(cls, part: str) -> MacroToken:
        """解析范围。"""
        parts = part.split("-", 1)
        if len(parts) != 2:
            raise ValueError(f"无效的范围格式: {part}")

        try:
            lower = int(parts[0])
            upper = int(parts[1])
        except ValueError:
            raise ValueError(f"范围边界必须是整数: {part}")

        if lower > upper:
            raise ValueError(f"范围下界必须小于上界: {part}")

        return MacroToken(type=TokenType.RANGE, value=(lower, upper), raw=part)

    @classmethod
    def _parse_number(cls, part: str) -> MacroToken:
        """解析数值。"""
        try:
            value = int(part)
            return MacroToken(type=TokenType.NUMBER, value=value, raw=part)
        except ValueError:
            raise ValueError(f"无效的数值: {part}")

    @classmethod
    def _parse_boolean(cls, part: str) -> MacroToken:
        """解析布尔值。"""
        value = part == "true"
        return MacroToken(type=TokenType.BOOLEAN, value=value, raw=part)

    @classmethod
    def _is_number(cls, part: str) -> bool:
        """检查是否为数值。"""
        if part.startswith("-"):
            return part[1:].isdigit() if len(part) > 1 else False
        return part.isdigit()

    @classmethod
    def _is_identifier(cls, part: str) -> bool:
        """检查是否为标识符（小写字母、数字、下划线）。"""
        if not part:
            return False
        return bool(re.match(r"^[a-z][a-z0-9_]*$", part))
