"""Infer null token sentinels present in the data."""

from __future__ import annotations

from collections.abc import Sequence

from duckdb import DuckDBPyConnection

from shared.db.sql import quote_identifier, quote_string
from suggestion.constants import NULL_TOKEN_CANDIDATES


def infer_null_tokens(
    conn: DuckDBPyConnection,
    *,
    table_name: str,
    columns: Sequence[str],
) -> tuple[str, ...]:
    """Return which known null sentinel strings actually appear in the data."""
    if not columns:
        return ()

    candidates_in = ", ".join(quote_string(c) for c in NULL_TOKEN_CANDIDATES)
    parts = []
    for col_name in columns:
        quoted = quote_identifier(col_name)
        val_expr = f"LOWER(TRIM(CAST({quoted} AS VARCHAR)))"
        parts.append(
            f"SELECT DISTINCT {val_expr} AS val "
            f"FROM {table_name} WHERE {val_expr} IN ({candidates_in})"
        )

    rows = conn.execute(" UNION ".join(parts)).fetchall()
    found = {row[0] for row in rows}
    return tuple(sorted(c for c in NULL_TOKEN_CANDIDATES if c in found))
