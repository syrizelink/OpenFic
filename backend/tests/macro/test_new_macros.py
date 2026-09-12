# -*- coding: utf-8 -*-
"""Uji makro kondisional."""

from app.macro.evaluator import MacroEvaluator
from app.macro.types import MacroContext


class TestConditionalBlocks:
    """Uji blok render kondisional."""

    def test_if_true_renders_content(self):
        """Uji isi dirender saat kondisi bernilai benar."""
        context = MacroContext()
        context.variables["show"] = True
        evaluator = MacroEvaluator(context)

        text = "Start {{if::show}}This is visible{{endif}} End"
        result = evaluator.evaluate_text(text)

        assert result == "Start This is visible End"

    def test_if_false_hides_content(self):
        """Uji isi disembunyikan saat kondisi bernilai salah."""
        context = MacroContext()
        context.variables["show"] = False
        evaluator = MacroEvaluator(context)

        text = "Start {{if::show}}This is hidden{{endif}} End"
        result = evaluator.evaluate_text(text)

        assert result == "Start  End"

    def test_if_undefined_variable_hides_content(self):
        """Uji isi disembunyikan saat variabel tidak terdefinisi."""
        context = MacroContext()
        evaluator = MacroEvaluator(context)

        text = "Start {{if::undefined}}This is hidden{{endif}} End"
        result = evaluator.evaluate_text(text)

        assert result == "Start  End"

    def test_if_non_bool_variable_hides_content(self):
        """Uji isi disembunyikan saat variabel bukan bertipe bool."""
        context = MacroContext()
        context.variables["count"] = 5
        evaluator = MacroEvaluator(context)

        text = "Start {{if::count}}This is hidden{{endif}} End"
        result = evaluator.evaluate_text(text)

        assert result == "Start  End"

    def test_nested_if_blocks(self):
        """Uji blok if bersarang."""
        context = MacroContext()
        context.variables["outer"] = True
        context.variables["inner"] = True
        evaluator = MacroEvaluator(context)

        text = "{{if::outer}}Outer {{if::inner}}Inner{{endif}} End{{endif}}"
        result = evaluator.evaluate_text(text)

        assert result == "Outer Inner End"

    def test_multiple_if_blocks(self):
        """Uji beberapa blok if yang independen."""
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
        """Uji jalur kondisi tidak sah tidak di-parse sebagai makro if."""
        evaluator = MacroEvaluator(MacroContext())

        text = "{{if::invalid::path}}hidden{{endif}}"
        result = evaluator.evaluate_text(text)

        assert result == ""
