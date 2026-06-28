# -*- coding: utf-8 -*-
"""条件宏测试。"""

from app.macro.evaluator import MacroEvaluator
from app.macro.types import MacroContext


class TestConditionalBlocks:
    """测试条件渲染块。"""

    def test_if_true_renders_content(self):
        """测试条件为真时渲染内容。"""
        context = MacroContext()
        context.variables["show"] = True
        evaluator = MacroEvaluator(context)

        text = "Start {{if::show}}This is visible{{endif}} End"
        result = evaluator.evaluate_text(text)

        assert result == "Start This is visible End"

    def test_if_false_hides_content(self):
        """测试条件为假时隐藏内容。"""
        context = MacroContext()
        context.variables["show"] = False
        evaluator = MacroEvaluator(context)

        text = "Start {{if::show}}This is hidden{{endif}} End"
        result = evaluator.evaluate_text(text)

        assert result == "Start  End"

    def test_if_undefined_variable_hides_content(self):
        """测试未定义变量时隐藏内容。"""
        context = MacroContext()
        evaluator = MacroEvaluator(context)

        text = "Start {{if::undefined}}This is hidden{{endif}} End"
        result = evaluator.evaluate_text(text)

        assert result == "Start  End"

    def test_if_non_bool_variable_hides_content(self):
        """测试非 bool 类型变量时隐藏内容。"""
        context = MacroContext()
        context.variables["count"] = 5
        evaluator = MacroEvaluator(context)

        text = "Start {{if::count}}This is hidden{{endif}} End"
        result = evaluator.evaluate_text(text)

        assert result == "Start  End"

    def test_nested_if_blocks(self):
        """测试嵌套的 if 块。"""
        context = MacroContext()
        context.variables["outer"] = True
        context.variables["inner"] = True
        evaluator = MacroEvaluator(context)

        text = "{{if::outer}}Outer {{if::inner}}Inner{{endif}} End{{endif}}"
        result = evaluator.evaluate_text(text)

        assert result == "Outer Inner End"

    def test_multiple_if_blocks(self):
        """测试多个独立的 if 块。"""
        context = MacroContext()
        context.variables["first"] = True
        context.variables["second"] = False
        context.variables["third"] = True
        evaluator = MacroEvaluator(context)

        text = (
            "{{if::first}}A{{endif}} {{if::second}}B{{endif}} {{if::third}}C{{endif}}"
        )
        result = evaluator.evaluate_text(text)

        assert result == "A  C"

    def test_if_rejects_invalid_condition_path(self):
        """测试非法条件路径不作为 if 宏解析。"""
        evaluator = MacroEvaluator(MacroContext())

        text = "{{if::invalid::path}}hidden{{endif}}"
        result = evaluator.evaluate_text(text)

        assert result == ""
