# -*- coding: utf-8 -*-
"""
Naming helpers for retrieval resources.
"""

import hashlib


def make_table_name(index_key: str) -> str:
    digest = hashlib.sha1(index_key.encode("utf-8")).hexdigest()[:12]
    return f"idx_{digest}"


def quote_sql(value: str) -> str:
    return value.replace("'", "''")
