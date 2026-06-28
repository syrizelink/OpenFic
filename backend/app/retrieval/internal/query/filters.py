# -*- coding: utf-8 -*-
"""
Filter expression helpers for retrieval queries.
"""

from typing import Any

from app.retrieval.internal.common.naming import quote_sql


def build_eq_filter(field: str, value: Any) -> str:
    return f"{field} = {render_value(value)}"


def render_value(value: Any) -> str:
    if isinstance(value, str):
        return f"'{quote_sql(value)}'"
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "NULL"
    return str(value)
