# -*- coding: utf-8 -*-
"""
Conditional Handler - 条件渲染宏处理器。

支持：
- {{if::condition_var}} ... {{endif}} - 条件渲染块（使用上下文 bool 变量）

注意：if/endif 是块级宏，需要特殊处理。
- condition_var 必须是 MacroContext.variables 中的 bool 类型变量
"""

from app.macro.handlers.base import MacroHandler, MacroValidateError, MacroEvaluateError
from app.macro.types import MacroContext, MacroNode, TokenType


class IfHandler(MacroHandler):
    """if 宏处理器（块开始标记）。"""

    def validate(self, node: MacroNode) -> None:
        """验证 if 宏参数。"""
        if len(node.args) != 1:
            raise MacroValidateError(
                f"if 宏需要 1 个参数，收到 {len(node.args)} 个",
                node,
            )

        first_arg = node.args[0]

        if first_arg.type != TokenType.IDENTIFIER:
            raise MacroValidateError(
                f"if 第一个参数必须是 identifier，收到 {first_arg.type.value}",
                node,
            )

    def evaluate(self, node: MacroNode, context: MacroContext) -> str:
        """
        求值 if 宏。

        注意：if 宏本身不返回内容，它只是一个标记。
        实际的条件判断和内容渲染由 evaluator 处理。
        """
        self.validate(node)

        first_arg = node.args[0]

        var_name = first_arg.value
        var_value: str | int | bool | None = context.variables.get(var_name)

        if var_value is None:
            raise MacroEvaluateError(
                f"变量未定义: {var_name}",
                node,
            )

        if not isinstance(var_value, bool):
            raise MacroEvaluateError(
                f"if 宏的条件变量必须是 bool 类型，变量 '{var_name}' 的类型是 {type(var_value).__name__}",
                node,
            )

        return "true" if var_value else "false"


class EndIfHandler(MacroHandler):
    """endif 宏处理器（块结束标记）。"""

    def validate(self, node: MacroNode) -> None:
        """验证 endif 宏参数。"""
        if len(node.args) != 0:
            raise MacroValidateError(
                f"endif 宏不需要参数，收到 {len(node.args)} 个",
                node,
            )

    def evaluate(self, node: MacroNode, context: MacroContext) -> str:
        """求值 endif 宏。"""
        self.validate(node)
        return ""
