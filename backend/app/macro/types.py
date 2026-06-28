# -*- coding: utf-8 -*-
"""
Macro Types - 宏类型定义。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TokenType(str, Enum):
    """宏参数 Token 类型。"""

    IDENTIFIER = "identifier"
    NUMBER = "number"
    RANGE = "range"
    STRING = "string"
    LIST = "list"
    BOOLEAN = "boolean"


@dataclass
class MacroToken:
    """
    宏参数 Token。

    Attributes:
        type: Token 类型。
        value: Token 值（根据类型不同，可能是 str、int、tuple[int, int]、list[str]）。
        raw: 原始文本。
    """

    type: TokenType
    value: Any
    raw: str


@dataclass
class MacroNode:
    """
    宏 AST 节点。

    Attributes:
        name: 宏名（如 "getmem"、"getworld"）。
        args: 参数列表。
        raw: 原始宏文本（包含 {{ }}）。
        start: 在源文本中的起始位置。
        end: 在源文本中的结束位置。
    """

    name: str
    args: list[MacroToken]
    raw: str
    start: int
    end: int


@dataclass
class MacroResult:
    """
    宏求值结果。

    Attributes:
        value: 求值结果（字符串形式）。
        original: 原始宏文本。
        start: 在源文本中的起始位置。
        end: 在源文本中的结束位置。
    """

    value: str
    original: str
    start: int
    end: int


@dataclass
class ChapterContext:
    """
    章节上下文（用于 getmem 宏）。

    Attributes:
        project_id: 项目 ID。
        chapter_id: 当前章节 ID。
        latest_field: 最新章节内容。
        near_field: 近场内容。
        mid_field: 中场内容。
        far_field: 远场内容。
        chapter_list_field: 最新章节列表。
    """

    project_id: str
    chapter_id: str
    latest_field: str = ""
    near_field: str = ""
    mid_field: str = ""
    far_field: str = ""
    chapter_list_field: str = "[]"


@dataclass
class WorldContext:
    """世界书上下文（用于 getworld 宏）。"""

    content: str = ""


@dataclass
class MacroContext:
    """
    宏求值上下文。

    Attributes:
        variables: 变量字典（if 条件使用）。
        chapter_context: 章节上下文（getmem 使用）。
        world_context: 世界书上下文（getworld 使用）。
    """

    variables: dict[str, str | int | bool] = field(default_factory=dict)
    chapter_context: ChapterContext | None = None
    world_context: WorldContext | None = None
