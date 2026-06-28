# -*- coding: utf-8 -*-
"""
Macro 模块 - 宏解析与求值。

提供提示词链中宏表达式的解析、验证和求值功能。
"""

from app.macro.types import (
    MacroContext,
    MacroNode,
    MacroResult,
    MacroToken,
    TokenType,
)
from app.macro.lexer import MacroLexer
from app.macro.parser import MacroParser
from app.macro.evaluator import MacroEvaluator
from app.macro.registry import MACRO_REGISTRY, MacroMeta

__all__ = [
    # Types
    "MacroContext",
    "MacroNode",
    "MacroResult",
    "MacroToken",
    "TokenType",
    # Core
    "MacroLexer",
    "MacroParser",
    "MacroEvaluator",
    # Registry
    "MACRO_REGISTRY",
    "MacroMeta",
]
