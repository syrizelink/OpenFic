# -*- coding: utf-8 -*-
"""
Macro Evaluator Tests - 宏求值器测试。
"""

import json

from app.macro.evaluator import MacroEvaluator
from app.macro.types import ChapterContext, MacroContext, WorldContext


class TestEvaluateGetmem:
    """测试 getmem 宏求值。"""

    def test_getmem_far(self):
        """获取远场记忆。"""
        context = MacroContext(
            chapter_context=ChapterContext(
                project_id="proj1",
                chapter_id="chap1",
                far_field='[{"start_order":1,"end_order":10,"summary":"远场内容"}]',
                mid_field="中场内容",
                near_field="近场内容",
            )
        )
        evaluator = MacroEvaluator(context)

        result = evaluator.evaluate_text("{{getmem::chapter::far}}")
        assert json.loads(result) == [
            {"start_order": 1, "end_order": 10, "summary": "远场内容"}
        ]

    def test_getmem_middle(self):
        """获取中场记忆。"""
        context = MacroContext(
            chapter_context=ChapterContext(
                project_id="proj1",
                chapter_id="chap1",
                far_field="远场内容",
                mid_field='[{"order":1,"title":"第一章","summary":"中场内容"}]',
                near_field="近场内容",
            )
        )
        evaluator = MacroEvaluator(context)

        result = evaluator.evaluate_text("{{getmem::chapter::middle}}")
        assert json.loads(result) == [
            {"order": 1, "title": "第一章", "summary": "中场内容"}
        ]

    def test_getmem_near(self):
        """获取近场记忆。"""
        context = MacroContext(
            chapter_context=ChapterContext(
                project_id="proj1",
                chapter_id="chap1",
                far_field="远场内容",
                mid_field="中场内容",
                near_field='[{"order":9,"title":"第九章","content":"近场内容","word_count":4}]',
            )
        )
        evaluator = MacroEvaluator(context)

        result = evaluator.evaluate_text("{{getmem::chapter::near}}")
        assert json.loads(result) == [
            {"order": 9, "title": "第九章", "content": "近场内容", "word_count": 4}
        ]

    def test_getmem_latest(self):
        """获取最新章节内容。"""
        context = MacroContext(
            chapter_context=ChapterContext(
                project_id="proj1",
                chapter_id="chap1",
                far_field="远场内容",
                mid_field="中场内容",
                near_field="近场内容",
                latest_field='{"order":10,"title":"第十章","content":"这是最新章节的完整正文内容。","word_count":13}',
            )
        )
        evaluator = MacroEvaluator(context)

        result = evaluator.evaluate_text("{{getmem::chapter::latest}}")
        assert json.loads(result) == {
            "order": 10,
            "title": "第十章",
            "content": "这是最新章节的完整正文内容。",
            "word_count": 13,
        }

    def test_getlist(self):
        """获取章节列表。"""
        context = MacroContext(
            chapter_context=ChapterContext(
                project_id="proj1",
                chapter_id="chap1",
                chapter_list_field='[{"order":10,"title":"第十章"}]',
            )
        )
        evaluator = MacroEvaluator(context)

        result = evaluator.evaluate_text("{{getlist}}")
        assert json.loads(result) == [{"order": 10, "title": "第十章"}]

    def test_getmem_no_context(self):
        """无章节上下文应保留原文。"""
        evaluator = MacroEvaluator()

        text = "{{getmem::chapter::far}}"
        result = evaluator.evaluate_text(text)

        assert result == text

    def test_getworld(self):
        """获取世界书内容。"""
        context = MacroContext(
            world_context=WorldContext(content="<角色>\n林舟\n</角色>")
        )
        evaluator = MacroEvaluator(context)

        result = evaluator.evaluate_text("{{getworld}}")

        assert result == "<角色>\n林舟\n</角色>"

    def test_getworld_no_context(self):
        """无世界书上下文应保留原文。"""
        evaluator = MacroEvaluator()

        text = "{{getworld}}"
        result = evaluator.evaluate_text(text)

        assert result == text


class TestEvaluateText:
    """测试完整文本求值。"""

    def test_no_macros(self):
        """无宏文本原样返回。"""
        evaluator = MacroEvaluator()

        text = "Plain text without macros"
        result = evaluator.evaluate_text(text)

        assert result == text

    def test_unknown_macros_are_skipped(self):
        """未知宏保留原文。"""
        evaluator = MacroEvaluator()

        text = "{{unknown::value}}"
        result = evaluator.evaluate_text(text)

        assert result == text
