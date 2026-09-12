# -*- coding: utf-8 -*-
"""
Macro Lexer Tests - uji lexer makro.
"""

import pytest

from app.macro.lexer import MacroLexer
from app.macro.types import TokenType


class TestFindMacros:
    """Uji pencarian kecocokan makro."""

    def test_find_single_macro(self):
        """Mencari satu makro."""
        text = "Hello {{getmem::chapter::near}} world"
        matches = MacroLexer.find_macros(text)

        assert len(matches) == 1
        assert matches[0].body == "getmem::chapter::near"
        assert matches[0].raw == "{{getmem::chapter::near}}"

    def test_find_multiple_macros(self):
        """Mencari beberapa makro."""
        text = "{{getmem::chapter::near}} and {{getmem::chapter::far}}"
        matches = MacroLexer.find_macros(text)

        assert len(matches) == 2
        assert matches[0].body == "getmem::chapter::near"
        assert matches[1].body == "getmem::chapter::far"

    def test_ignore_nested_braces(self):
        """Makro di dalam kurung kurawal bersarang juga ikut tercocokkan."""
        text = "{{{invalid}}} and {{valid::arg}}"
        matches = MacroLexer.find_macros(text)

        # Catatan: {{invalid}} di dalam {{{invalid}}} juga ikut tercocokkan
        assert len(matches) == 2
        assert matches[0].body == "invalid"
        assert matches[1].body == "valid::arg"

    def test_ignore_multiline(self):
        """Mengabaikan makro yang melintasi baris."""
        text = "{{multi\nline}} and {{single::line}}"
        matches = MacroLexer.find_macros(text)

        assert len(matches) == 1
        assert matches[0].body == "single::line"

    def test_empty_text(self):
        """Teks kosong mengembalikan daftar kosong."""
        matches = MacroLexer.find_macros("")
        assert len(matches) == 0


class TestTokenizeArgs:
    """Uji parsing argumen."""

    def test_identifier(self):
        """Parsing identifier."""
        tokens = MacroLexer.tokenize_args("var_name")

        assert len(tokens) == 1
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "var_name"

    def test_number_positive(self):
        """Parsing bilangan bulat positif."""
        tokens = MacroLexer.tokenize_args("100")

        assert len(tokens) == 1
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[0].value == 100

    def test_number_negative(self):
        """Parsing bilangan bulat negatif."""
        tokens = MacroLexer.tokenize_args("-50")

        assert len(tokens) == 1
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[0].value == -50

    def test_range(self):
        """Parsing rentang."""
        tokens = MacroLexer.tokenize_args("1-100")

        assert len(tokens) == 1
        assert tokens[0].type == TokenType.RANGE
        assert tokens[0].value == (1, 100)

    def test_string(self):
        """Parsing string."""
        tokens = MacroLexer.tokenize_args('"hello world"')

        assert len(tokens) == 1
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == "hello world"

    def test_string_with_escaped_quotes(self):
        """Parsing string dengan tanda kutip ter-escape."""
        tokens = MacroLexer.tokenize_args('"say \\"hello\\""')

        assert len(tokens) == 1
        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == 'say "hello"'

    def test_list(self):
        """Parsing daftar."""
        tokens = MacroLexer.tokenize_args("list(a,b,c)")

        assert len(tokens) == 1
        assert tokens[0].type == TokenType.LIST
        assert tokens[0].value == ["a", "b", "c"]

    def test_multiple_args(self):
        """Parsing beberapa argumen."""
        tokens = MacroLexer.tokenize_args('var_name::"value"')

        assert len(tokens) == 2
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "var_name"
        assert tokens[1].type == TokenType.STRING
        assert tokens[1].value == "value"

    def test_string_with_separator(self):
        """:: di dalam string tidak boleh dianggap pemisah."""
        tokens = MacroLexer.tokenize_args('"contains::separator"')

        assert len(tokens) == 1
        assert tokens[0].value == "contains::separator"

    def test_invalid_range_order(self):
        """Batas bawah rentang harus lebih kecil dari batas atas."""
        with pytest.raises(ValueError, match="lebih kecil dari batas atas"):
            MacroLexer.tokenize_args("100-50")

    def test_empty_list(self):
        """Daftar kosong harus memunculkan error."""
        with pytest.raises(ValueError, match="List tidak boleh kosong"):
            MacroLexer.tokenize_args("list()")
