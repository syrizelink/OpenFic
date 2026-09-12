# -*- coding: utf-8 -*-
"""
Macro Types - definisi tipe makro.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TokenType(str, Enum):
    """Tipe Token argumen makro."""

    IDENTIFIER = "identifier"
    NUMBER = "number"
    RANGE = "range"
    STRING = "string"
    LIST = "list"
    BOOLEAN = "boolean"


@dataclass
class MacroToken:
    """
    Token argumen makro.

    Attributes:
        type: Tipe Token.
        value: Nilai Token (tergantung tipenya, bisa berupa str, int,
            tuple[int, int], atau list[str]).
        raw: Teks asli.
    """

    type: TokenType
    value: Any
    raw: str


@dataclass
class MacroNode:
    """
    Node AST makro.

    Attributes:
        name: Nama makro (misalnya "getmem", "getworld").
        args: Daftar argumen.
        raw: Teks makro asli (termasuk {{ }}).
        start: Posisi awal di teks sumber.
        end: Posisi akhir di teks sumber.
    """

    name: str
    args: list[MacroToken]
    raw: str
    start: int
    end: int


@dataclass
class MacroResult:
    """
    Hasil evaluasi makro.

    Attributes:
        value: Hasil evaluasi (dalam bentuk string).
        original: Teks makro asli.
        start: Posisi awal di teks sumber.
        end: Posisi akhir di teks sumber.
    """

    value: str
    original: str
    start: int
    end: int


@dataclass
class ChapterContext:
    """
    Konteks bab (dipakai oleh makro getmem).

    Attributes:
        project_id: ID proyek.
        chapter_id: ID bab saat ini.
        latest_field: Isi bab terbaru.
        near_field: Isi medan dekat.
        mid_field: Isi medan menengah.
        far_field: Isi medan jauh.
        chapter_list_field: Daftar bab terbaru.
    """

    project_id: str
    chapter_id: str
    latest_field: str = ""
    near_field: str = ""
    mid_field: str = ""
    far_field: str = ""
    chapter_list_field: str = "[]"


@dataclass
class WorldContext:
    """Konteks buku dunia (dipakai oleh makro getworld)."""

    content: str = ""


@dataclass
class MacroContext:
    """
    Konteks evaluasi makro.

    Attributes:
        variables: Kamus variabel (dipakai oleh kondisi if).
        chapter_context: Konteks bab (dipakai oleh getmem).
        world_context: Konteks buku dunia (dipakai oleh getworld).
    """

    variables: dict[str, str | int | bool] = field(default_factory=dict)
    chapter_context: ChapterContext | None = None
    world_context: WorldContext | None = None
