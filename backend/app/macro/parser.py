# -*- coding: utf-8 -*-
"""
Macro Parser - pengurai sintaks makro.

Bertugas mengurai isi makro menjadi node AST.
"""

from app.macro.lexer import MacroLexer, MacroMatch
from app.macro.registry import is_valid_macro
from app.macro.types import MacroNode


class MacroParseError(Exception):
    """Kesalahan penguraian makro."""

    def __init__(self, message: str, raw: str):
        super().__init__(message)
        self.raw = raw


class MacroParser:
    """Pengurai sintaks makro."""

    @classmethod
    def parse(cls, match: MacroMatch) -> MacroNode:
        """
        Mengurai hasil pencocokan makro menjadi node AST.

        Args:
            match: Hasil pencocokan makro.

        Returns:
            Node AST makro.

        Raises:
            MacroParseError: Kesalahan penguraian.
        """
        body = match.body

        parts = body.split("::", 1)
        name = parts[0].strip()

        if not name:
            raise MacroParseError("Nama makro tidak boleh kosong", match.raw)

        if not is_valid_macro(name):
            raise MacroParseError(f"Nama makro tidak dikenal: {name}", match.raw)

        args_str = parts[1] if len(parts) > 1 else ""

        try:
            args = MacroLexer.tokenize_args(args_str)
        except ValueError as e:
            raise MacroParseError(str(e), match.raw)

        if name == "getmem":
            from app.macro.handlers.mem_handler import GetMemHandler

            try:
                GetMemHandler().validate(
                    MacroNode(
                        name=name,
                        args=args,
                        raw=match.raw,
                        start=match.start,
                        end=match.end,
                    )
                )
            except Exception as exc:
                raise MacroParseError(str(exc), match.raw) from exc

        if name == "getlist":
            from app.macro.handlers.mem_handler import GetListHandler

            try:
                GetListHandler().validate(
                    MacroNode(
                        name=name,
                        args=args,
                        raw=match.raw,
                        start=match.start,
                        end=match.end,
                    )
                )
            except Exception as exc:
                raise MacroParseError(str(exc), match.raw) from exc

        if name == "getworld":
            from app.macro.handlers.mem_handler import GetWorldHandler

            try:
                GetWorldHandler().validate(
                    MacroNode(
                        name=name,
                        args=args,
                        raw=match.raw,
                        start=match.start,
                        end=match.end,
                    )
                )
            except Exception as exc:
                raise MacroParseError(str(exc), match.raw) from exc

        return MacroNode(
            name=name,
            args=args,
            raw=match.raw,
            start=match.start,
            end=match.end,
        )

    @classmethod
    def parse_all(cls, text: str) -> list[MacroNode]:
        """
        Mengurai semua makro yang valid di dalam teks.

        Args:
            text: Teks sumber.

        Returns:
            Daftar node AST makro (hanya yang berhasil diurai).
        """
        matches = MacroLexer.find_macros(text)
        nodes = []

        for match in matches:
            try:
                node = cls.parse(match)
                nodes.append(node)
            except MacroParseError:
                pass

        return nodes

    @classmethod
    def try_parse(cls, match: MacroMatch) -> MacroNode | None:
        """
        Mencoba mengurai hasil pencocokan makro, mengembalikan None jika gagal.

        Args:
            match: Hasil pencocokan makro.

        Returns:
            Node AST makro, atau None (penguraian gagal).
        """
        try:
            return cls.parse(match)
        except MacroParseError:
            return None
