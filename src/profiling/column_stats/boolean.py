"""Boolean profiling stats."""

from __future__ import annotations

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.sql import execute_scalar, nullish_predicate, quote_identifier, quote_string
from shared.models.profiling import BooleanColumnProfile, ColumnCounts


def compute_boolean_column_profile(
    conn: DuckDBPyConnection,
    column_name: str,
    true_tokens: tuple[str, ...],
    false_tokens: tuple[str, ...],
    null_tokens: tuple[str, ...],
    counts: ColumnCounts,
) -> BooleanColumnProfile:
    """Count true/false/unrecognized values for a boolean column."""
    quoted = quote_identifier(column_name)
    normalized = f"LOWER(TRIM(CAST({quoted} AS VARCHAR)))"
    nullish = nullish_predicate(quoted, null_tokens)

    true_in = _in_clause(true_tokens)
    false_in = _in_clause(false_tokens)

    row = conn.execute(
        f"SELECT COUNT(*) FILTER (WHERE {normalized} IN ({true_in})),"
        f" COUNT(*) FILTER (WHERE {normalized} IN ({false_in}))"
        f" FROM {RAW_INPUT_TABLE_NAME} WHERE NOT ({nullish})"
    ).fetchone()
    true_token_count: int = row[0]  # type: ignore[index]
    false_token_count: int = row[1]  # type: ignore[index]

    non_nullish = counts.non_nullish_count
    unrecognized_count = non_nullish - true_token_count - false_token_count
    recognized_ratio = 1.0 if non_nullish <= 0 else (
        (true_token_count + false_token_count) / non_nullish
    )

    return BooleanColumnProfile(
        true_token_count=true_token_count,
        false_token_count=false_token_count,
        unrecognized_count=unrecognized_count,
        recognized_ratio=recognized_ratio,
    )


def _in_clause(tokens: tuple[str, ...]) -> str:
    normalized = sorted({token.strip().lower() for token in tokens if token.strip()})
    if not normalized:
        return "''"
    return ", ".join(quote_string(token) for token in normalized)
