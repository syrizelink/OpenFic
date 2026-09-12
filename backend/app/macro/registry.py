# -*- coding: utf-8 -*-
"""
Macro Registry - registri makro.

Mendefinisikan himpunan nama makro bawaan beserta meta-informasinya.
"""

from dataclasses import dataclass


@dataclass
class MacroMeta:
    """
    Meta-informasi makro.

    Attributes:
        name: Nama makro.
        configurable: Apakah dapat dikonfigurasi di panel samping.
        description: Deskripsi.
        handler_class: Nama kelas handler (dimuat secara lazy).
    """

    name: str
    configurable: bool
    description: str
    handler_class: str


MACRO_REGISTRY: dict[str, MacroMeta] = {
    "getmem": MacroMeta(
        name="getmem",
        configurable=False,
        description="Mengambil isi memori bab",
        handler_class="GetMemHandler",
    ),
    "getlist": MacroMeta(
        name="getlist",
        configurable=False,
        description="Mengambil daftar isi 50 bab terbaru",
        handler_class="GetListHandler",
    ),
    "getworld": MacroMeta(
        name="getworld",
        configurable=False,
        description="Mengambil entri buku dunia proyek saat ini yang permanen dan cocok kata kunci",
        handler_class="GetWorldHandler",
    ),
    "if": MacroMeta(
        name="if",
        configurable=True,
        description="Awal blok render kondisional (berbasis variabel bool)",
        handler_class="IfHandler",
    ),
    "endif": MacroMeta(
        name="endif",
        configurable=True,
        description="Akhir blok render kondisional",
        handler_class="EndIfHandler",
    ),
}


def get_macro_names() -> set[str]:
    """Mengambil semua nama makro bawaan."""
    return set(MACRO_REGISTRY.keys())


def is_valid_macro(name: str) -> bool:
    """Memeriksa apakah nama makro valid."""
    return name in MACRO_REGISTRY


def is_configurable(name: str) -> bool:
    """Memeriksa apakah makro dapat dikonfigurasi."""
    meta = MACRO_REGISTRY.get(name)
    return meta.configurable if meta else False
