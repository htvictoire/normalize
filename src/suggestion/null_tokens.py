"""Infer null token sentinels present in the data.

Shared across strategies: both rule-based and AI resolve null tokens with this
same deterministic scan (the AI path keeps this in our code rather than asking
the model). The candidate constant is co-located here since this is its only
consumer.
"""

from __future__ import annotations

from collections.abc import Sequence

# Known sentinel strings commonly used to represent missing values.
NULL_TOKEN_CANDIDATES = frozenset({
    "n/a", "na", "null", "none", "nan", "nil", "-", "--", "---", "?", "missing",
})


def infer_null_tokens(
    rows: list[list[str]],
    columns: Sequence[str],
) -> tuple[str, ...]:
    """Return which known null sentinel strings actually appear in the rows."""
    col_count = len(columns)
    found: set[str] = set()
    for row in rows:
        for i in range(min(len(row), col_count)):
            val = row[i].strip().lower()
            if val in NULL_TOKEN_CANDIDATES:
                found.add(val)
    return tuple(sorted(c for c in NULL_TOKEN_CANDIDATES if c in found))
