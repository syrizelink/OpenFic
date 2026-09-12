# -*- coding: utf-8 -*-
"""
Macro Evaluator Tests - uji evaluator makro.
"""

import json

from app.macro.evaluator import MacroEvaluator
from app.macro.types import ChapterContext, MacroContext, WorldContext


class TestEvaluateGetmem:
    """Uji evaluasi makro getmem."""

    def test_getmem_far(self):
        """Mengambil memori medan jauh."""
        context = MacroContext(
            chapter_context=ChapterContext(
                project_id="proj1",
                chapter_id="chap1",
                far_field='[{"start_order":1,"end_order":10,"summary":"Isi medan jauh"}]',
                mid_field="Isi medan menengah",
                near_field="Isi medan dekat",
            )
        )
        evaluator = MacroEvaluator(context)

        result = evaluator.evaluate_text("{{getmem::chapter::far}}")
        assert json.loads(result) == [
            {"start_order": 1, "end_order": 10, "summary": "Isi medan jauh"}
        ]

    def test_getmem_middle(self):
        """Mengambil memori medan menengah."""
        context = MacroContext(
            chapter_context=ChapterContext(
                project_id="proj1",
                chapter_id="chap1",
                far_field="Isi medan jauh",
                mid_field='[{"order":1,"title":"Bab 1","summary":"Isi medan menengah"}]',
                near_field="Isi medan dekat",
            )
        )
        evaluator = MacroEvaluator(context)

        result = evaluator.evaluate_text("{{getmem::chapter::middle}}")
        assert json.loads(result) == [
            {"order": 1, "title": "Bab 1", "summary": "Isi medan menengah"}
        ]

    def test_getmem_near(self):
        """Mengambil memori medan dekat."""
        context = MacroContext(
            chapter_context=ChapterContext(
                project_id="proj1",
                chapter_id="chap1",
                far_field="Isi medan jauh",
                mid_field="Isi medan menengah",
                near_field='[{"order":9,"title":"Bab 9","content":"Isi medan dekat","word_count":4}]',
            )
        )
        evaluator = MacroEvaluator(context)

        result = evaluator.evaluate_text("{{getmem::chapter::near}}")
        assert json.loads(result) == [
            {"order": 9, "title": "Bab 9", "content": "Isi medan dekat", "word_count": 4}
        ]

    def test_getmem_latest(self):
        """Mengambil isi bab terbaru."""
        context = MacroContext(
            chapter_context=ChapterContext(
                project_id="proj1",
                chapter_id="chap1",
                far_field="Isi medan jauh",
                mid_field="Isi medan menengah",
                near_field="Isi medan dekat",
                latest_field='{"order":10,"title":"Bab 10","content":"Ini adalah isi utama lengkap dari bab terbaru.","word_count":13}',
            )
        )
        evaluator = MacroEvaluator(context)

        result = evaluator.evaluate_text("{{getmem::chapter::latest}}")
        assert json.loads(result) == {
            "order": 10,
            "title": "Bab 10",
            "content": "Ini adalah isi utama lengkap dari bab terbaru.",
            "word_count": 13,
        }

    def test_getlist(self):
        """Mengambil daftar bab."""
        context = MacroContext(
            chapter_context=ChapterContext(
                project_id="proj1",
                chapter_id="chap1",
                chapter_list_field='[{"order":10,"title":"Bab 10"}]',
            )
        )
        evaluator = MacroEvaluator(context)

        result = evaluator.evaluate_text("{{getlist}}")
        assert json.loads(result) == [{"order": 10, "title": "Bab 10"}]

    def test_getmem_no_context(self):
        """Tanpa konteks bab, teks asli harus dipertahankan."""
        evaluator = MacroEvaluator()

        text = "{{getmem::chapter::far}}"
        result = evaluator.evaluate_text(text)

        assert result == text

    def test_getworld(self):
        """Mengambil isi buku dunia."""
        context = MacroContext(
            world_context=WorldContext(content="<tokoh>\nLinu\n</tokoh>")
        )
        evaluator = MacroEvaluator(context)

        result = evaluator.evaluate_text("{{getworld}}")

        assert result == "<tokoh>\nLinu\n</tokoh>"

    def test_getworld_no_context(self):
        """Tanpa konteks buku dunia, teks asli harus dipertahankan."""
        evaluator = MacroEvaluator()

        text = "{{getworld}}"
        result = evaluator.evaluate_text(text)

        assert result == text


class TestEvaluateText:
    """Uji evaluasi teks lengkap."""

    def test_no_macros(self):
        """Teks tanpa makro dikembalikan apa adanya."""
        evaluator = MacroEvaluator()

        text = "Plain text without macros"
        result = evaluator.evaluate_text(text)

        assert result == text

    def test_unknown_macros_are_skipped(self):
        """Makro tak dikenal mempertahankan teks asli."""
        evaluator = MacroEvaluator()

        text = "{{unknown::value}}"
        result = evaluator.evaluate_text(text)

        assert result == text
