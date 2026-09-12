import re
from dataclasses import replace

from app.agent_runtime.context.types import ContextMessage

_SURROGATE_RE = re.compile(r"[\ud800-\udfff]")


def sanitize_surrogates(parts: list[ContextMessage]) -> list[ContextMessage]:
    """Membuang setengah kode surrogate Unicode dari content; mengembalikan daftar
    baru tanpa mengubah argumen masukan."""
    out: list[ContextMessage] = []
    for p in parts:
        if p.content and _SURROGATE_RE.search(p.content):
            out.append(replace(p, content=_SURROGATE_RE.sub("", p.content)))
        else:
            out.append(p)
    return out
