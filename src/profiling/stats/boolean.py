"""Boolean profiling stats."""

from __future__ import annotations

from duckdb import DuckDBPyConnection

from shared.db.sql import quote_identifier, quote_string
from shared.models.profiling import BooleanColumnProfile


def compute_boolean_column_profile(
    conn: DuckDBPyConnection,
    *,
    column_name: str,
    true_tokens: tuple[str, ...],
    false_tokens: tuple[str, ...],
    null_tokens: tuple[str, ...],
    non_null_count: int,
) -> BooleanColumnProfile:
    """Count true/false/unrecognized values for a boolean column."""
    quoted = quote_identifier(column_name)
    normalized = f"LOWER(TRIM(CAST({quoted} AS VARCHAR)))"
    nullish = _nullish_predicate(quoted, null_tokens)

    true_in = _in_clause(true_tokens)
    false_in = _in_clause(false_tokens)

    true_row = conn.execute(
        f"SELECT COUNT(*) FROM raw_input WHERE NOT ({nullish}) AND {normalized} IN ({true_in})"
    ).fetchone()
    if true_row is None:
        raise RuntimeError("true token count query returned no rows")
    true_token_count = int(true_row[0])

    false_row = conn.execute(
        f"SELECT COUNT(*) FROM raw_input WHERE NOT ({nullish}) AND {normalized} IN ({false_in})"
    ).fetchone()
    if false_row is None:
        raise RuntimeError("false token count query returned no rows")
    false_token_count = int(false_row[0])
    unrecognized_count = max(non_null_count - true_token_count - false_token_count, 0)
    recognized_ratio = 1.0 if non_null_count <= 0 else (
        (true_token_count + false_token_count) / non_null_count
    )

    return BooleanColumnProfile(
        true_token_count=true_token_count,
        false_token_count=false_token_count,
        unrecognized_count=unrecognized_count,
        non_nullish_count=non_null_count,
        recognized_ratio=recognized_ratio,
    )


def _in_clause(tokens: tuple[str, ...]) -> str:
    normalized = sorted({token.strip().lower() for token in tokens if token.strip()})
    if not normalized:
        return "''"
    return ", ".join(quote_string(token) for token in normalized)


def _nullish_predicate(value_expr: str, null_tokens: tuple[str, ...]) -> str:
    base = f"NULLIF(TRIM(CAST({value_expr} AS VARCHAR)), '')"
    normalized_tokens = sorted({token.strip().lower() for token in null_tokens if token.strip()})
    if not normalized_tokens:
        return f"{base} IS NULL"
    in_clause = ", ".join(quote_string(token) for token in normalized_tokens)
    return f"{base} IS NULL OR LOWER(TRIM(CAST({value_expr} AS VARCHAR))) IN ({in_clause})"
