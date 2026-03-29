"""Boolean expression builder."""

from __future__ import annotations

from collections.abc import Sequence

from conversion.cells.exprs.column_exprs import ColumnExprs
from conversion.cells.exprs.nullish import token_in_clause


def build_boolean_exprs(
    nullish_predicate: str,
    normalized_raw_value: str,
    true_tokens: Sequence[str],
    false_tokens: Sequence[str],
    issue_label: str = "INVALID_BOOLEAN",
) -> ColumnExprs:
    """Build ColumnExprs for a boolean column."""
    true_in = token_in_clause(true_tokens)
    false_in = token_in_clause(false_tokens)
    true_match = f"{normalized_raw_value} IN ({true_in})"
    false_match = f"{normalized_raw_value} IN ({false_in})"
    normalized = (
        f"CASE WHEN {nullish_predicate} THEN NULL "
        f"WHEN {true_match} THEN TRUE "
        f"WHEN {false_match} THEN FALSE "
        "ELSE NULL END"
    )
    issue = (
        f"CASE WHEN {nullish_predicate} THEN NULL "
        f"WHEN {true_match} OR {false_match} THEN NULL "
        f"ELSE '{issue_label}' END"
    )
    return ColumnExprs(parse_cte_entries=(), normalized_expr=normalized, issue_expr=issue)
