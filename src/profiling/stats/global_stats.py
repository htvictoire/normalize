"""Global profiling stats."""

from __future__ import annotations

from duckdb import DuckDBPyConnection

from shared.db.sql import quote_identifier, quote_string, validate_identifier


def compute_global_stats(
    conn: DuckDBPyConnection,
    *,
    table_name: str,
    null_tokens: tuple[str, ...],
) -> tuple[int, int]:
    """Return (row_count, empty_row_count)."""
    validate_identifier(table_name)
    count_row = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
    if count_row is None:
        raise RuntimeError("row count query returned no rows")
    row_count = int(count_row[0])

    cols = [str(row[1]) for row in conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()]
    if not cols:
        return (row_count, row_count)

    predicates = [_nullish_predicate(quote_identifier(col), null_tokens) for col in cols]
    empty_row = conn.execute(
        f"SELECT COUNT(*) FROM {table_name} WHERE {' AND '.join(predicates)}"
    ).fetchone()
    if empty_row is None:
        raise RuntimeError("empty row count query returned no rows")
    empty_row_count = int(empty_row[0])
    return (row_count, empty_row_count)


def _nullish_predicate(value_expr: str, null_tokens: tuple[str, ...]) -> str:
    base = f"NULLIF(TRIM(CAST({value_expr} AS VARCHAR)), '')"
    normalized_tokens = sorted({token.strip().lower() for token in null_tokens if token.strip()})
    if not normalized_tokens:
        return f"{base} IS NULL"
    in_clause = ", ".join(quote_string(token) for token in normalized_tokens)
    return f"{base} IS NULL OR LOWER(TRIM(CAST({value_expr} AS VARCHAR))) IN ({in_clause})"
