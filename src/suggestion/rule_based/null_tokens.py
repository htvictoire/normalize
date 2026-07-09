"""Infer null token sentinels present in the data.

This is a heuristic guess (fixed candidate list matched against sampled
values), the same category as delimiter/header detection — not a mechanical
fact, so it lives here rather than in the shared suggestion.constants.
"""

from __future__ import annotations

from collections.abc import Sequence

from suggestion.rule_based.constants import NULL_TOKEN_CANDIDATES


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
