"""Nullish predicate and boolean token helpers."""

from __future__ import annotations

from collections.abc import Sequence

from shared.db.sql import quote_string


def build_nullish_predicate(
    value_expr: str,
    normalized_value_expr: str,
    null_tokens: Sequence[str],
) -> str:
    """Build SQL predicate that matches configured nullish values."""
    base_value = f"NULLIF(TRIM({value_expr}), '')"
    normalized_tokens = sorted(
        {token.strip().lower() for token in null_tokens if token.strip()}
    )
    if not normalized_tokens:
        return f"{base_value} IS NULL"
    in_clause = ", ".join(quote_string(token) for token in normalized_tokens)
    return f"{base_value} IS NULL OR {normalized_value_expr} IN ({in_clause})"


def token_in_clause(tokens: Sequence[str]) -> str:
    if not tokens:
        raise ValueError("EMPTY_BOOLEAN_TOKEN_SET")
    return ", ".join(quote_string(token) for token in tokens)
