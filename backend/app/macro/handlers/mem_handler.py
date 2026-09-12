# -*- coding: utf-8 -*-
"""
Mem Handler - handler makro pengambilan memori.

Mendukung:
- {{getmem::chapter::latest}} - mengambil isi utama bab terbaru
- {{getmem::chapter::far}} - mengambil memori bab medan jauh
- {{getmem::chapter::middle}} - mengambil memori bab medan menengah
- {{getmem::chapter::near}} - mengambil memori bab medan dekat
"""

from app.macro.handlers.base import MacroHandler, MacroEvaluateError, MacroValidateError
from app.macro.types import MacroContext, MacroNode, TokenType


VALID_LEVEL1 = {"chapter"}
VALID_CHAPTER_FIELDS = {"far", "middle", "near", "latest"}


class GetMemHandler(MacroHandler):
    """Handler makro getmem."""

    def validate(self, node: MacroNode) -> None:
        """Memvalidasi argumen makro getmem."""
        if len(node.args) != 2:
            raise MacroValidateError(
                f"Makro getmem membutuhkan 2 argumen (tipe, field), menerima"
                f" {len(node.args)}",
                node,
            )

        for i, arg in enumerate(node.args):
            if arg.type != TokenType.IDENTIFIER:
                raise MacroValidateError(
                    f"Argumen ke-{i + 1} getmem harus berupa identifier,"
                    f" menerima {arg.type.value}",
                    node,
                )

        level1 = node.args[0].value
        if level1 not in VALID_LEVEL1:
            raise MacroValidateError(
                f"Argumen tingkat pertama getmem harus salah satu dari {VALID_LEVEL1},"
                f" menerima {level1}",
                node,
            )

        level2 = node.args[1].value
        if level1 == "chapter" and level2 not in VALID_CHAPTER_FIELDS:
            raise MacroValidateError(
                f"Argumen tingkat kedua getmem::chapter harus salah satu dari"
                f" {VALID_CHAPTER_FIELDS}, menerima {level2}",
                node,
            )

    def evaluate(self, node: MacroNode, context: MacroContext) -> str:
        """Mengevaluasi makro getmem."""
        self.validate(node)

        if context.chapter_context is None:
            raise MacroEvaluateError(
                "Konteks bab belum diatur, memori tidak dapat diambil", node
            )

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

        raise MacroEvaluateError(f"Jalur memori tidak dikenal: {level1}::{level2}", node)


class GetListHandler(MacroHandler):
    """Handler makro getlist."""

    def validate(self, node: MacroNode) -> None:
        """Memvalidasi argumen makro getlist."""
        if node.args:
            raise MacroValidateError("Makro getlist tidak menerima argumen", node)

    def evaluate(self, node: MacroNode, context: MacroContext) -> str:
        """Mengevaluasi makro getlist."""
        self.validate(node)
        if context.chapter_context is None:
            raise MacroEvaluateError(
                "Konteks bab belum diatur, daftar bab tidak dapat diambil", node
            )
        return context.chapter_context.chapter_list_field


class GetWorldHandler(MacroHandler):
    """Handler makro getworld."""

    def validate(self, node: MacroNode) -> None:
        """Memvalidasi argumen makro getworld."""
        if node.args:
            raise MacroValidateError("Makro getworld tidak menerima argumen", node)

    def evaluate(self, node: MacroNode, context: MacroContext) -> str:
        """Mengevaluasi makro getworld."""
        self.validate(node)
        if context.world_context is None:
            raise MacroEvaluateError(
                "Konteks buku dunia belum diatur, isi buku dunia tidak dapat diambil",
                node,
            )
        return context.world_context.content
