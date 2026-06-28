# -*- coding: utf-8 -*-
"""
Mem Handler - 记忆获取宏处理器。

支持：
- {{getmem::chapter::latest}} - 获取最新章节原文
- {{getmem::chapter::far}} - 获取远场章节记忆
- {{getmem::chapter::middle}} - 获取中场章节记忆
- {{getmem::chapter::near}} - 获取近场章节记忆
"""

from app.macro.handlers.base import MacroHandler, MacroEvaluateError, MacroValidateError
from app.macro.types import MacroContext, MacroNode, TokenType


VALID_LEVEL1 = {"chapter"}
VALID_CHAPTER_FIELDS = {"far", "middle", "near", "latest"}


class GetMemHandler(MacroHandler):
    """getmem 宏处理器。"""

    def validate(self, node: MacroNode) -> None:
        """验证 getmem 宏参数。"""
        if len(node.args) != 2:
            raise MacroValidateError(
                f"getmem 宏需要 2 个参数（类型、字段），收到 {len(node.args)} 个",
                node,
            )

        for i, arg in enumerate(node.args):
            if arg.type != TokenType.IDENTIFIER:
                raise MacroValidateError(
                    f"getmem 第 {i + 1} 个参数必须是 identifier，收到 {arg.type.value}",
                    node,
                )

        level1 = node.args[0].value
        if level1 not in VALID_LEVEL1:
            raise MacroValidateError(
                f"getmem 第一级参数必须是 {VALID_LEVEL1}，收到 {level1}",
                node,
            )

        level2 = node.args[1].value
        if level1 == "chapter" and level2 not in VALID_CHAPTER_FIELDS:
            raise MacroValidateError(
                f"getmem::chapter 第二级参数必须是 {VALID_CHAPTER_FIELDS}，收到 {level2}",
                node,
            )

    def evaluate(self, node: MacroNode, context: MacroContext) -> str:
        """求值 getmem 宏。"""
        self.validate(node)

        if context.chapter_context is None:
            raise MacroEvaluateError("未设置章节上下文，无法获取记忆", node)

        level1 = node.args[0].value
        level2 = node.args[1].value

        if level1 == "chapter":
            chapter_ctx = context.chapter_context
            if level2 == "latest":
                return chapter_ctx.latest_field
            elif level2 == "far":
                return chapter_ctx.far_field
            elif level2 == "middle":
                return chapter_ctx.mid_field
            elif level2 == "near":
                return chapter_ctx.near_field

        raise MacroEvaluateError(f"未知的记忆路径: {level1}::{level2}", node)


class GetListHandler(MacroHandler):
    """getlist 宏处理器。"""

    def validate(self, node: MacroNode) -> None:
        """验证 getlist 宏参数。"""
        if node.args:
            raise MacroValidateError("getlist 宏不接受参数", node)

    def evaluate(self, node: MacroNode, context: MacroContext) -> str:
        """求值 getlist 宏。"""
        self.validate(node)
        if context.chapter_context is None:
            raise MacroEvaluateError("未设置章节上下文，无法获取章节列表", node)
        return context.chapter_context.chapter_list_field


class GetWorldHandler(MacroHandler):
    """getworld 宏处理器。"""

    def validate(self, node: MacroNode) -> None:
        """验证 getworld 宏参数。"""
        if node.args:
            raise MacroValidateError("getworld 宏不接受参数", node)

    def evaluate(self, node: MacroNode, context: MacroContext) -> str:
        """求值 getworld 宏。"""
        self.validate(node)
        if context.world_context is None:
            raise MacroEvaluateError("未设置世界书上下文，无法获取世界书内容", node)
        return context.world_context.content
