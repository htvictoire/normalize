"""Per-column SQL expression output contract for cell normalization transforms."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ColumnExprs:
    """SQL expressions produced by one column's transform builder.

    ``parse_cte_entries`` — (alias, expr) pairs to materialise in the parse CTE.
    ``normalized_expr``   — expression that yields the typed, normalised value.
    ``issue_expr``        — expression that yields an issue code string or NULL.
    """

    parse_cte_entries: tuple[tuple[str, str], ...]
    normalized_expr: str
    issue_expr: str
