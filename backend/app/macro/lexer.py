# -*- coding: utf-8 -*-
"""
Macro Lexer - penganalisis leksikal makro.

Bertugas mengenali ekspresi makro di dalam teks dan mengurai argumen makro.
"""

import re
from dataclasses import dataclass

from app.macro.types import MacroToken, TokenType


@dataclass
class MacroMatch:
    """
    Hasil pencocokan makro.

    Attributes:
        body: Isi makro (tanpa {{ }}).
        raw: Teks asli (dengan {{ }}).
        start: Posisi awal di teks sumber.
        end: Posisi akhir di teks sumber.
    """

    body: str
    raw: str
    start: int
    end: int


class MacroLexer:
    """Penganalisis leksikal makro."""

    MACRO_PATTERN = re.compile(r"\{\{([^{}]+)\}\}")
    SEPARATOR = "::"

    @classmethod
    def find_macros(cls, text: str) -> list[MacroMatch]:
        """
        Mencari semua ekspresi makro di dalam teks.

        Args:
            text: Teks sumber.

        Returns:
            Daftar hasil pencocokan makro.
        """
        matches = []
        for m in cls.MACRO_PATTERN.finditer(text):
            body = m.group(1).strip()
            if body and "\n" not in body:
                matches.append(
                    MacroMatch(
                        body=body,
                        raw=m.group(0),
                        start=m.start(),
                        end=m.end(),
                    )
                )
        return matches

    @classmethod
    def tokenize_args(cls, args_str: str) -> list[MacroToken]:
        """
        Mengurai string argumen menjadi daftar Token.

        Args:
            args_str: String argumen (misalnya "var_name::\"value\"").

        Returns:
            Daftar Token.

        Raises:
            ValueError: Format argumen salah.
        """
        if not args_str:
            return []

        tokens = []
        parts = cls._split_args(args_str)

        for part in parts:
            token = cls._parse_token(part)
            tokens.append(token)

        return tokens

    @classmethod
    def _split_args(cls, args_str: str) -> list[str]:
        """
        Memisahkan argumen dengan ::, tetapi tetap memperhitungkan :: di dalam string.

        Args:
            args_str: String argumen.

        Returns:
            Daftar argumen hasil pemisahan.
        """
        parts = []
        current = ""
        in_string = False
        i = 0

        while i < len(args_str):
            char = args_str[i]

            if char == '"' and (i == 0 or args_str[i - 1] != "\\"):
                in_string = not in_string
                current += char
            elif not in_string and args_str[i : i + 2] == cls.SEPARATOR:
                if current:
                    parts.append(current.strip())
                current = ""
                i += 1
            else:
                current += char

            i += 1

        if current:
            parts.append(current.strip())

        return parts

    @classmethod
    def _parse_token(cls, part: str) -> MacroToken:
        """
        Mengurai satu argumen menjadi Token.

        Args:
            part: String argumen.

        Returns:
            Token hasil penguraian.

        Raises:
            ValueError: Format argumen salah.
        """
        part = part.strip()

        if part.startswith('"') and part.endswith('"'):
            return cls._parse_string(part)

        if part.startswith("list(") and part.endswith(")"):
            return cls._parse_list(part)

        if part in ("true", "false"):
            return cls._parse_boolean(part)

        if "-" in part and not part.startswith("-"):
            return cls._parse_range(part)

        if cls._is_number(part):
            return cls._parse_number(part)

        if cls._is_identifier(part):
            return MacroToken(type=TokenType.IDENTIFIER, value=part, raw=part)

        raise ValueError(f"Tidak dapat mengurai argumen: {part}")

    @classmethod
    def _parse_string(cls, part: str) -> MacroToken:
        """Mengurai literal string."""
        content = part[1:-1]
        unescaped = content.replace('\\"', '"')
        return MacroToken(type=TokenType.STRING, value=unescaped, raw=part)

    @classmethod
    def _parse_list(cls, part: str) -> MacroToken:
        """Mengurai list."""
        content = part[5:-1]
        if not content:
            raise ValueError("List tidak boleh kosong")

        items = [item.strip() for item in content.split(",")]
        if any(not item for item in items):
            raise ValueError("Item list tidak boleh kosong")

        return MacroToken(type=TokenType.LIST, value=items, raw=part)

    @classmethod
    def _parse_range(cls, part: str) -> MacroToken:
        """Mengurai rentang."""
        parts = part.split("-", 1)
        if len(parts) != 2:
            raise ValueError(f"Format rentang tidak valid: {part}")

        try:
            lower = int(parts[0])
            upper = int(parts[1])
        except ValueError:
            raise ValueError(f"Batas rentang harus berupa bilangan bulat: {part}")

        if lower > upper:
            raise ValueError(f"Batas bawah rentang harus lebih kecil dari batas atas: {part}")

        return MacroToken(type=TokenType.RANGE, value=(lower, upper), raw=part)

    @classmethod
    def _parse_number(cls, part: str) -> MacroToken:
        """Mengurai nilai numerik."""
        try:
            value = int(part)
            return MacroToken(type=TokenType.NUMBER, value=value, raw=part)
        except ValueError:
            raise ValueError(f"Nilai numerik tidak valid: {part}")

    @classmethod
    def _parse_boolean(cls, part: str) -> MacroToken:
        """Mengurai nilai boolean."""
        value = part == "true"
        return MacroToken(type=TokenType.BOOLEAN, value=value, raw=part)

    @classmethod
    def _is_number(cls, part: str) -> bool:
        """Memeriksa apakah berupa nilai numerik."""
        if part.startswith("-"):
            return part[1:].isdigit() if len(part) > 1 else False
        return part.isdigit()

    @classmethod
    def _is_identifier(cls, part: str) -> bool:
        """Memeriksa apakah berupa identifier (huruf kecil, angka, garis bawah)."""
        if not part:
            return False
        return bool(re.match(r"^[a-z][a-z0-9_]*$", part))
