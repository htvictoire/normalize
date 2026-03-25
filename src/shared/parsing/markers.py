"""SQL expression helpers for sign marker detection and stripping."""

from __future__ import annotations

import re

from shared.db.sql import quote_string


def has_marker(trimmed: str, marker: str) -> str:
    """Return a SQL boolean expression: true when ``trimmed`` starts or ends with ``marker``."""
    m = re.escape(marker.lower())
    at_start = f"REGEXP_FULL_MATCH(LOWER({trimmed}), {quote_string(rf'^{m}\s*.+$')})"
    at_end = f"REGEXP_FULL_MATCH(LOWER({trimmed}), {quote_string(rf'^.+\s*{m}$')})"
    return f"({at_start} OR {at_end})"


def strip_marker(trimmed: str, marker: str) -> str:
    """Return a SQL expression stripping ``marker`` from the start or end of ``trimmed``."""
    m = re.escape(marker.lower())
    at_start = f"REGEXP_FULL_MATCH(LOWER({trimmed}), {quote_string(rf'^{m}\s*.+$')})"
    from_start = f"TRIM(REGEXP_REPLACE(LOWER({trimmed}), {quote_string(rf'^{m}\s*')}, ''))"
    from_end = f"TRIM(REGEXP_REPLACE(LOWER({trimmed}), {quote_string(rf'\s*{m}$')}, ''))"
    return f"CASE WHEN {at_start} THEN {from_start} ELSE {from_end} END"
