# -*- coding: utf-8 -*-
"""
Serialization helpers for retrieval rows.
"""

import json
from typing import Any


def serialize_metadata(metadata: dict[str, Any] | None) -> str:
    return json.dumps(metadata or {}, ensure_ascii=False, separators=(",", ":"))


def deserialize_metadata(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}
