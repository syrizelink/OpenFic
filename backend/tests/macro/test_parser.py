# -*- coding: utf-8 -*-
"""
Macro Parser Tests - 宏语法解析器测试。
"""

import pytest

from app.macro.lexer import MacroMatch
from app.macro.parser import MacroParser, MacroParseError


class TestParseMacro:
    """测试宏解析。"""

    def test_parse_getmem(self):
        """解析 getmem 宏。"""
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
        """解析 getlist 宏。"""
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
        """解析 getworld 宏。"""
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
        """getworld 不接受参数。"""
        match = MacroMatch(
            body="getworld::chapter",
            raw="{{getworld::chapter}}",
            start=0,
            end=22,
        )
        with pytest.raises(MacroParseError, match="getworld 宏不接受参数"):
            MacroParser.parse(match)

    def test_getlist_args_raise_error(self):
        """getlist 不接受参数。"""
        match = MacroMatch(
            body="getlist::chapter",
            raw="{{getlist::chapter}}",
            start=0,
            end=20,
        )
        with pytest.raises(MacroParseError, match="getlist 宏不接受参数"):
            MacroParser.parse(match)

    def test_unknown_macro_raises_error(self):
        """未知宏名应报错。"""
        match = MacroMatch(
            body="unknown_macro::arg",
            raw="{{unknown_macro::arg}}",
            start=0,
            end=22,
        )
        with pytest.raises(MacroParseError, match="未知的宏名"):
            MacroParser.parse(match)

    def test_getmem_current_raises_error(self):
        """已移除的 getmem current 字段应报错。"""
        match = MacroMatch(
            body="getmem::chapter::current",
            raw="{{getmem::chapter::current}}",
            start=0,
            end=27,
        )
        with pytest.raises(MacroParseError, match="getmem::chapter 第二级参数"):
            MacroParser.parse(match)

    def test_empty_macro_name_raises_error(self):
        """空宏名应报错。"""
        match = MacroMatch(
            body="::arg",
            raw="{{::arg}}",
            start=0,
            end=9,
        )
        with pytest.raises(MacroParseError, match="宏名不能为空"):
            MacroParser.parse(match)


class TestParseAll:
    """测试批量解析。"""

    def test_parse_all_valid(self):
        """解析所有有效宏。"""
        text = "{{getmem::chapter::near}} and {{getmem::chapter::far}}"
        nodes = MacroParser.parse_all(text)

        assert len(nodes) == 2
        assert nodes[0].name == "getmem"
        assert nodes[1].name == "getmem"

    def test_skip_invalid_macros(self):
        """跳过无效宏。"""
        text = "{{invalid::macro}} and {{getmem::chapter::near}}"
        nodes = MacroParser.parse_all(text)

        assert len(nodes) == 1
        assert nodes[0].name == "getmem"


class TestTryParse:
    """测试安全解析。"""

    def test_try_parse_valid(self):
        """有效宏返回节点。"""
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
        """无效宏返回 None。"""
        match = MacroMatch(
            body="unknown::arg",
            raw="{{unknown::arg}}",
            start=0,
            end=16,
        )
        node = MacroParser.try_parse(match)

        assert node is None
