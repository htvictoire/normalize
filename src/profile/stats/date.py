"""Date profile stats."""

from __future__ import annotations

from profile.models import DateColumnProfile

from duckdb import DuckDBPyConnection

from shared.db.sql import quote_identifier, quote_string


def compute_date_column_profile(
    conn: DuckDBPyConnection,
    *,
    column_name: str,
    date_format: str,
    null_tokens: tuple[str, ...],
    non_null_count: int,
) -> DateColumnProfile:
    """Count rows parseable by configured date format."""
    quoted = quote_identifier(column_name)
    if date_format == "EXCEL_SERIAL":
        date_expr = f"(DATE '1899-12-30' + TRY_CAST({quoted} AS INTEGER))"
    else:
        date_expr = f"TRY_CAST(TRY_STRPTIME({quoted}, {quote_string(date_format)}) AS DATE)"

    nullish = _nullish_predicate(quoted, null_tokens)
    match_row = conn.execute(
        "SELECT COUNT(*) FROM raw_input "
        f"WHERE NOT ({nullish}) AND {date_expr} IS NOT NULL"
    ).fetchone()
    if match_row is None:
        raise RuntimeError("date format match count query returned no rows")
    format_match_count = int(match_row[0])

    format_match_ratio = 1.0 if non_null_count <= 0 else (format_match_count / non_null_count)
    return DateColumnProfile(
        format_match_count=format_match_count,
        non_nullish_count=non_null_count,
        format_match_ratio=format_match_ratio,
    )


def _nullish_predicate(value_expr: str, null_tokens: tuple[str, ...]) -> str:
    base = f"NULLIF(TRIM(CAST({value_expr} AS VARCHAR)), '')"
    normalized_tokens = sorted({token.strip().lower() for token in null_tokens if token.strip()})
    if not normalized_tokens:
        return f"{base} IS NULL"
    in_clause = ", ".join(quote_string(token) for token in normalized_tokens)
    return f"{base} IS NULL OR LOWER(TRIM(CAST({value_expr} AS VARCHAR))) IN ({in_clause})"
