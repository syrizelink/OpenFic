# -*- coding: utf-8 -*-
"""
Macro Lexer Tests - 宏词法分析器测试。
"""

import pytest

from app.macro.lexer import MacroLexer
from app.macro.types import TokenType


class TestFindMacros:
    """测试宏匹配查找。"""

    def test_find_single_macro(self):
        """查找单个宏。"""
        text = "Hello {{getmem::chapter::near}} world"
        matches = MacroLexer.find_macros(text)

        assert len(matches) == 1
        assert matches[0].body == "getmem::chapter::near"
        assert matches[0].raw == "{{getmem::chapter::near}}"

    def test_find_multiple_macros(self):
        """查找多个宏。"""
        text = "{{getmem::chapter::near}} and {{getmem::chapter::far}}"
        matches = MacroLexer.find_macros(text)

        assert len(matches) == 2
        assert matches[0].body == "getmem::chapter::near"
        assert matches[1].body == "getmem::chapter::far"

    def test_ignore_nested_braces(self):
        """嵌套大括号中的宏也会被匹配。"""
        text = "{{{invalid}}} and {{valid::arg}}"
        matches = MacroLexer.find_macros(text)

        # 注意：{{{invalid}}} 中的 {{invalid}} 也会被匹配
        assert len(matches) == 2
        assert matches[0].body == "invalid"
        assert matches[1].body == "valid::arg"

    def test_ignore_multiline(self):
        """忽略跨行宏。"""
        text = "{{multi\nline}} and {{single::line}}"
        matches = MacroLexer.find_macros(text)

        assert len(matches) == 1
        assert matches[0].body == "single::line"

    def test_empty_text(self):
        """空文本返回空列表。"""
        matches = MacroLexer.find_macros("")
        assert len(matches) == 0


class TestTokenizeArgs:
    """测试参数解析。"""

    def test_identifier(self):
        """解析标识符。"""
        tokens = MacroLexer.tokenize_args("var_name")

        assert len(tokens) == 1
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "var_name"

    def test_number_positive(self):
        """解析正整数。"""
        tokens = MacroLexer.tokenize_args("100")

        assert len(tokens) == 1
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[0].value == 100

    def test_number_negative(self):
        """解析负整数。"""
        tokens = MacroLexer.tokenize_args("-50")

        assert len(tokens) == 1
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[0].value == -50

    def test_range(self):
        """解析范围。"""
        tokens = MacroLexer.tokenize_args("1-100")

        assert len(tokens) == 1
        assert tokens[0].type == TokenType.RANGE
        assert tokens[0].value == (1, 100)

    def test_string(self):
        """解析字符串。"""
        tokens = MacroLexer.tokenize_args('"hello world"')

        assert len(tokens) == 1
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == "hello world"

    def test_string_with_escaped_quotes(self):
        """解析带转义引号的字符串。"""
        tokens = MacroLexer.tokenize_args('"say \\"hello\\""')

        assert len(tokens) == 1
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == 'say "hello"'

    def test_list(self):
        """解析列表。"""
        tokens = MacroLexer.tokenize_args("list(a,b,c)")

        assert len(tokens) == 1
        assert tokens[0].type == TokenType.LIST
        assert tokens[0].value == ["a", "b", "c"]

    def test_multiple_args(self):
        """解析多个参数。"""
        tokens = MacroLexer.tokenize_args('var_name::"value"')

        assert len(tokens) == 2
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "var_name"
        assert tokens[1].type == TokenType.STRING
        assert tokens[1].value == "value"

    def test_string_with_separator(self):
        """字符串内的 :: 不应作为分隔符。"""
        tokens = MacroLexer.tokenize_args('"contains::separator"')

        assert len(tokens) == 1
        assert tokens[0].value == "contains::separator"

    def test_invalid_range_order(self):
        """范围下界必须小于上界。"""
        with pytest.raises(ValueError, match="下界必须小于上界"):
            MacroLexer.tokenize_args("100-50")

    def test_empty_list(self):
        """空列表应报错。"""
        with pytest.raises(ValueError, match="列表不能为空"):
            MacroLexer.tokenize_args("list()")
