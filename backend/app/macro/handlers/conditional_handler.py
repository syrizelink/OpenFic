# -*- coding: utf-8 -*-
"""
Conditional Handler - handler makro render kondisional.

Mendukung:
- {{if::condition_var}} ... {{endif}} - blok render kondisional (memakai variabel bool konteks)

Catatan: if/endif adalah makro tingkat blok sehingga perlu penanganan khusus.
- condition_var harus berupa variabel bertipe bool di MacroContext.variables
"""

from app.macro.handlers.base import MacroHandler, MacroValidateError, MacroEvaluateError
from app.macro.types import MacroContext, MacroNode, TokenType


class IfHandler(MacroHandler):
    """Handler makro if (penanda awal blok)."""

    def validate(self, node: MacroNode) -> None:
        """Memvalidasi argumen makro if."""
        if len(node.args) != 1:
            raise MacroValidateError(
                f"Makro if membutuhkan 1 argumen, menerima {len(node.args)}",
                node,
            )

        first_arg = node.args[0]

        if first_arg.type != TokenType.IDENTIFIER:
            raise MacroValidateError(
                f"Argumen pertama if harus berupa identifier,"
                f" menerima {first_arg.type.value}",
                node,
            )

    def evaluate(self, node: MacroNode, context: MacroContext) -> str:
        """
        Mengevaluasi makro if.

        Catatan: makro if sendiri tidak mengembalikan isi, ia hanya sebuah penanda.
        Penilaian kondisi dan render isi yang sebenarnya ditangani oleh evaluator.
        """
        self.validate(node)

        first_arg = node.args[0]

        var_name = first_arg.value
        var_value: str | int | bool | None = context.variables.get(var_name)

        if var_value is None:
            raise MacroEvaluateError(
                f"Variabel belum didefinisikan: {var_name}",
                node,
            )

        if not isinstance(var_value, bool):
            raise MacroEvaluateError(
                f"Variabel kondisi makro if harus bertipe bool, tipe variabel"
                f" '{var_name}' adalah {type(var_value).__name__}",
                node,
            )

        return "true" if var_value else "false"


class EndIfHandler(MacroHandler):
    """Handler makro endif (penanda akhir blok)."""

    def validate(self, node: MacroNode) -> None:
        """Memvalidasi argumen makro endif."""
        if len(node.args) != 0:
            raise MacroValidateError(
                f"Makro endif tidak membutuhkan argumen, menerima {len(node.args)}",
                node,
            )

    def evaluate(self, node: MacroNode, context: MacroContext) -> str:
        """Mengevaluasi makro endif."""
        self.validate(node)
        return ""
