"""Boolean expression builder."""

from __future__ import annotations

from shared.db.sql import quote_string
from shared.parsing.boolean import BOOLEAN_FALSE_TOKENS, BOOLEAN_TRUE_TOKENS

from conversion.cells.exprs.column_exprs import ColumnExprs

_TRUE_IN = ", ".join(quote_string(t) for t in sorted(BOOLEAN_TRUE_TOKENS))
_FALSE_IN = ", ".join(quote_string(t) for t in sorted(BOOLEAN_FALSE_TOKENS))


def build_boolean_exprs(
    nullish_predicate: str,
    normalized_raw_value: str,
    issue_label: str = "INVALID_BOOLEAN",
) -> ColumnExprs:
    """Build ColumnExprs for a boolean column.

    ``normalized_raw_value`` is ``LOWER(TRIM(...))``, matching the lowercase tokens.
    A non-nullish value outside the vocabulary becomes NULL and is reported.
    """
    true_match = f"{normalized_raw_value} IN ({_TRUE_IN})"
    false_match = f"{normalized_raw_value} IN ({_FALSE_IN})"
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
