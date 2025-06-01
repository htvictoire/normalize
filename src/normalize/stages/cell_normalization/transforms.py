"""Expression builders for cell normalization SQL."""

from __future__ import annotations

from collections.abc import Sequence

from normalize.stages.cell_normalization.sql_helpers import (
    quote_identifier,
    quote_string,
)


def build_column_exprs(
    column_name: str,
    inferred_type: str,
    nullish_predicate: str,
    *,
    true_tokens: Sequence[str],
    false_tokens: Sequence[str],
) -> tuple[str, str]:
    """Build normalized-value and issue-code SQL expressions for one column."""
    quoted_column = quote_identifier(column_name)
    raw_value = f"CAST({quoted_column} AS VARCHAR)"
    normalized_raw_value = f"LOWER(TRIM({raw_value}))"

    if inferred_type == "string":
        normalized = f"CASE WHEN {nullish_predicate} THEN NULL ELSE {raw_value} END"
        return (normalized, "NULL")
    if inferred_type == "integer":
        normalized = (
            f"CASE WHEN {nullish_predicate} THEN NULL ELSE TRY_CAST({raw_value} AS BIGINT) END"
        )
        issue = (
            f"CASE WHEN {nullish_predicate} THEN NULL "
            f"WHEN TRY_CAST({raw_value} AS BIGINT) IS NULL THEN 'INVALID_INTEGER' "
            "ELSE NULL END"
        )
        return (normalized, issue)
    if inferred_type == "float":
        normalized = (
            f"CASE WHEN {nullish_predicate} THEN NULL ELSE TRY_CAST({raw_value} AS DOUBLE) END"
        )
        issue = (
            f"CASE WHEN {nullish_predicate} THEN NULL "
            f"WHEN TRY_CAST({raw_value} AS DOUBLE) IS NULL THEN 'INVALID_DECIMAL' "
            "ELSE NULL END"
        )
        return (normalized, issue)
    if inferred_type == "boolean":
        true_in_clause = _token_in_clause(true_tokens)
        false_in_clause = _token_in_clause(false_tokens)
        true_match = f"{normalized_raw_value} IN ({true_in_clause})"
        false_match = f"{normalized_raw_value} IN ({false_in_clause})"
        normalized = (
            f"CASE WHEN {nullish_predicate} THEN NULL "
            f"WHEN {true_match} THEN TRUE "
            f"WHEN {false_match} THEN FALSE "
            "ELSE NULL END"
        )
        issue = (
            f"CASE WHEN {nullish_predicate} THEN NULL "
            f"WHEN {true_match} OR {false_match} THEN NULL "
            "ELSE 'INVALID_BOOLEAN' END"
        )
        return (normalized, issue)

    raise ValueError(f"UNSUPPORTED_INFERRED_TYPE:{inferred_type}")


def build_nullish_predicate(column_name: str, null_tokens: Sequence[str]) -> str:
    """Build SQL predicate that matches configured nullish values."""
    quoted_column = quote_identifier(column_name)
    base_value = f"NULLIF(TRIM(CAST({quoted_column} AS VARCHAR)), '')"
    normalized_tokens = sorted(
        {token.strip().lower() for token in null_tokens if token.strip() != ""}
    )
    if not normalized_tokens:
        return f"{base_value} IS NULL"
    in_clause = ", ".join(quote_string(token) for token in normalized_tokens)
    return f"{base_value} IS NULL OR LOWER(TRIM(CAST({quoted_column} AS VARCHAR))) IN ({in_clause})"


def _token_in_clause(tokens: Sequence[str]) -> str:
    if not tokens:
        raise ValueError("EMPTY_BOOLEAN_TOKEN_SET")
    return ", ".join(quote_string(token) for token in tokens)
