"""Null/non-null profiling stats."""

from __future__ import annotations

from collections.abc import Sequence

from duckdb import DuckDBPyConnection

from shared.db.sql import quote_identifier, quote_string, validate_identifier


def compute_null_stats(
    conn: DuckDBPyConnection,
    *,
    table_name: str,
    column_names: list[str],
    null_tokens: tuple[str, ...],
) -> dict[str, tuple[int, int]]:
    """Return per-column (null_count, non_null_count) in one query."""
    validate_identifier(table_name)
    if not column_names:
        return {}

    exprs: list[str] = []
    for column_name in column_names:
        quoted = quote_identifier(column_name)
        nullish = _nullish_predicate(quoted, null_tokens)
        null_alias = quote_identifier(f"{column_name}__null_count")
        non_null_alias = quote_identifier(f"{column_name}__non_null_count")
        exprs.append(
            f"SUM(CASE WHEN {nullish} THEN 1 ELSE 0 END) AS {null_alias}"
        )
        exprs.append(
            f"SUM(CASE WHEN {nullish} THEN 0 ELSE 1 END) AS {non_null_alias}"
        )

    row = conn.execute(f"SELECT {', '.join(exprs)} FROM {table_name}").fetchone()
    if row is None:
        raise RuntimeError("null stats query returned no rows")

    stats: dict[str, tuple[int, int]] = {}
    offset = 0
    for column_name in column_names:
        stats[column_name] = (int(row[offset]), int(row[offset + 1]))
        offset += 2
    return stats


def _nullish_predicate(value_expr: str, null_tokens: Sequence[str]) -> str:
    base = f"NULLIF(TRIM(CAST({value_expr} AS VARCHAR)), '')"
    normalized_tokens = sorted({token.strip().lower() for token in null_tokens if token.strip()})
    if not normalized_tokens:
        return f"{base} IS NULL"
    in_clause = ", ".join(quote_string(token) for token in normalized_tokens)
    return f"{base} IS NULL OR LOWER(TRIM(CAST({value_expr} AS VARCHAR))) IN ({in_clause})"
