# -*- coding: utf-8 -*-
"""
Macro Handler Base - kelas dasar handler makro.
"""

from abc import ABC, abstractmethod

from app.macro.types import MacroContext, MacroNode


class MacroHandler(ABC):
    """Kelas dasar handler makro."""

    @abstractmethod
    def evaluate(self, node: MacroNode, context: MacroContext) -> str:
        """
        Mengevaluasi node makro.

        Args:
            node: Node AST makro.
            context: Konteks evaluasi.

        Returns:
            Hasil evaluasi (dalam bentuk string).

        Raises:
            MacroEvaluateError: Kesalahan evaluasi.
        """
        pass

    @abstractmethod
    def validate(self, node: MacroNode) -> None:
        """
        Memvalidasi argumen makro.

        Args:
            node: Node AST makro.

        Raises:
            MacroValidateError: Kesalahan validasi.
        """
        pass


class MacroEvaluateError(Exception):
    """Kesalahan evaluasi makro."""

    def __init__(self, message: str, node: MacroNode):
        super().__init__(message)
        self.node = node


class MacroValidateError(Exception):
    """Kesalahan validasi makro."""

    def __init__(self, message: str, node: MacroNode):
        super().__init__(message)
        self.node = node
