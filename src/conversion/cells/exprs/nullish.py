"""Nullish predicate and boolean token helpers."""

from __future__ import annotations

from collections.abc import Sequence

from shared.db.sql import normalize_tokens, quote_string


def build_nullish_predicate(
    value_expr: str,
    normalized_value_expr: str,
    null_tokens: Sequence[str],
) -> str:
    """Build SQL predicate that matches configured nullish values."""
    base_value = f"NULLIF(TRIM({value_expr}), '')"
    normalized_tokens = normalize_tokens(null_tokens)
    if not normalized_tokens:
        return f"{base_value} IS NULL"
    in_clause = ", ".join(quote_string(token) for token in normalized_tokens)
    return f"{base_value} IS NULL OR {normalized_value_expr} IN ({in_clause})"


def token_in_clause(tokens: Sequence[str]) -> str:
    normalized_tokens = normalize_tokens(tokens)
    if not normalized_tokens:
        raise ValueError("Boolean column has no true/false tokens configured")
    return ", ".join(quote_string(token) for token in normalized_tokens)
