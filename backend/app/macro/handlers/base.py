# -*- coding: utf-8 -*-
"""
Macro Handler Base - 宏处理器基类。
"""

from abc import ABC, abstractmethod

from app.macro.types import MacroContext, MacroNode


class MacroHandler(ABC):
    """宏处理器基类。"""

    @abstractmethod
    def evaluate(self, node: MacroNode, context: MacroContext) -> str:
        """
        求值宏节点。

        Args:
            node: 宏 AST 节点。
            context: 求值上下文。

        Returns:
            求值结果（字符串形式）。

        Raises:
            MacroEvaluateError: 求值错误。
        """
        pass

    @abstractmethod
    def validate(self, node: MacroNode) -> None:
        """
        验证宏参数。

        Args:
            node: 宏 AST 节点。

        Raises:
            MacroValidateError: 验证错误。
        """
        pass


class MacroEvaluateError(Exception):
    """宏求值错误。"""

    def __init__(self, message: str, node: MacroNode):
        super().__init__(message)
        self.node = node


class MacroValidateError(Exception):
    """宏验证错误。"""

    def __init__(self, message: str, node: MacroNode):
        super().__init__(message)
        self.node = node
