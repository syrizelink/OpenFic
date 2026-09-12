# -*- coding: utf-8 -*-
"""
Prompts - modul konfigurasi prompt bawaan.

Modul ini memuat konfigurasi prompt bawaan dari berkas YAML, dipakai untuk:
1. Menyediakan metadata prompt yang dikelompokkan per kategori bisnis
2. Memulihkan isi bawaan ketika pengguna mereset rantai prompt
3. Mengelola berkas YAML prompt bawaan untuk agen kustom
"""

from app.prompts.loader import (
    create_custom_agent_prompt_yaml,
    delete_custom_agent_prompt_yaml,
    get_prompt_chains_metadata,
    load_prompt_chain,
    reset_custom_agent_prompt_yaml,
    builtin_agent_prompt_id,
    custom_agent_prompt_id,
)

__all__ = [
    "create_custom_agent_prompt_yaml",
    "delete_custom_agent_prompt_yaml",
    "get_prompt_chains_metadata",
    "load_prompt_chain",
    "reset_custom_agent_prompt_yaml",
    "builtin_agent_prompt_id",
    "custom_agent_prompt_id",
]
