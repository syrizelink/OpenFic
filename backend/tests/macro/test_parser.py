# -*- coding: utf-8 -*-
"""
Macro Parser Tests - uji parser sintaks makro.
"""

import pytest

from app.macro.lexer import MacroMatch
from app.macro.parser import MacroParser, MacroParseError


class TestParseMacro:
    """Uji parsing makro."""

    def test_parse_getmem(self):
        """Parsing makro getmem."""
        match = MacroMatch(
            body="getmem::chapter::latest",
            raw="{{getmem::chapter::latest}}",
            start=0,
            end=27,
        )
        node = MacroParser.parse(match)

        assert node.name == "getmem"
        assert len(node.args) == 2
        assert node.args[0].value == "chapter"
        assert node.args[1].value == "latest"

    def test_parse_getlist(self):
        """Parsing makro getlist."""
        match = MacroMatch(
            body="getlist",
            raw="{{getlist}}",
            start=0,
            end=11,
        )
        node = MacroParser.parse(match)

        assert node.name == "getlist"
        assert node.args == []

    def test_parse_getworld(self):
        """Parsing makro getworld."""
        match = MacroMatch(
            body="getworld",
            raw="{{getworld}}",
            start=0,
            end=12,
        )
        node = MacroParser.parse(match)

        assert node.name == "getworld"
        assert node.args == []

    def test_getworld_args_raise_error(self):
        """getworld tidak menerima argumen."""
        match = MacroMatch(
            body="getworld::chapter",
            raw="{{getworld::chapter}}",
            start=0,
            end=22,
        )
        with pytest.raises(MacroParseError, match="Makro getworld tidak menerima argumen"):
            MacroParser.parse(match)

    def test_getlist_args_raise_error(self):
        """getlist tidak menerima argumen."""
        match = MacroMatch(
            body="getlist::chapter",
            raw="{{getlist::chapter}}",
            start=0,
            end=20,
        )
        with pytest.raises(MacroParseError, match="Makro getlist tidak menerima argumen"):
            MacroParser.parse(match)

    def test_unknown_macro_raises_error(self):
        """Nama makro tak dikenal harus memunculkan error."""
        match = MacroMatch(
            body="unknown_macro::arg",
            raw="{{unknown_macro::arg}}",
            start=0,
            end=22,
        )
        with pytest.raises(MacroParseError, match="Nama makro tidak dikenal"):
            MacroParser.parse(match)

    def test_getmem_current_raises_error(self):
        """Field getmem current yang sudah dihapus harus memunculkan error."""
        match = MacroMatch(
            body="getmem::chapter::current",
            raw="{{getmem::chapter::current}}",
            start=0,
            end=27,
        )
        with pytest.raises(
            MacroParseError, match="Argumen tingkat kedua getmem::chapter"
        ):
            MacroParser.parse(match)

    def test_empty_macro_name_raises_error(self):
        """Nama makro kosong harus memunculkan error."""
        match = MacroMatch(
            body="::arg",
            raw="{{::arg}}",
            start=0,
            end=9,
        )
        with pytest.raises(MacroParseError, match="Nama makro tidak boleh kosong"):
            MacroParser.parse(match)


class TestParseAll:
    """Uji parsing massal."""

    def test_parse_all_valid(self):
        """Parsing seluruh makro yang valid."""
        text = "{{getmem::chapter::near}} and {{getmem::chapter::far}}"
        nodes = MacroParser.parse_all(text)

        assert len(nodes) == 2
        assert nodes[0].name == "getmem"
        assert nodes[1].name == "getmem"

    def test_skip_invalid_macros(self):
        """Melewati makro yang tidak valid."""
        text = "{{invalid::macro}} and {{getmem::chapter::near}}"
        nodes = MacroParser.parse_all(text)

        assert len(nodes) == 1
        assert nodes[0].name == "getmem"


class TestTryParse:
    """Uji parsing aman."""

    def test_try_parse_valid(self):
        """Makro valid mengembalikan node."""
        match = MacroMatch(
            body="getmem::chapter::near",
            raw="{{getmem::chapter::near}}",
            start=0,
            end=25,
        )
        node = MacroParser.try_parse(match)

        assert node is not None
        assert node.name == "getmem"

    def test_try_parse_invalid(self):
        """Makro tidak valid mengembalikan None."""
        match = MacroMatch(
            body="unknown::arg",
            raw="{{unknown::arg}}",
            start=0,
            end=16,
        )
        node = MacroParser.try_parse(match)

        assert node is None
