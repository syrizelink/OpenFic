import re
from dataclasses import replace

from app.agent_runtime.context.types import ContextMessage

_SURROGATE_RE = re.compile(r"[\ud800-\udfff]")


def sanitize_surrogates(parts: list[ContextMessage]) -> list[ContextMessage]:
    """剔除 content 中的 Unicode surrogate 半码；返回新列表，不修改入参。"""
    out: list[ContextMessage] = []
    for p in parts:
        if p.content and _SURROGATE_RE.search(p.content):
            out.append(replace(p, content=_SURROGATE_RE.sub("", p.content)))
        else:
            out.append(p)
    return out
