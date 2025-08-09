"""Currency profile stats."""

from __future__ import annotations

from profile.models import CurrencyColumnProfile

from duckdb import DuckDBPyConnection

from shared.db.sql import quote_identifier, quote_string
from shared.utils.currency import build_currency_symbol_extract_expr


def compute_currency_column_profile(
    conn: DuckDBPyConnection,
    *,
    column_name: str,
    null_tokens: tuple[str, ...],
    non_null_count: int,
) -> CurrencyColumnProfile:
    """Compute symbol distribution and dominant symbol metrics."""
    quoted = quote_identifier(column_name)
    symbol_expr = build_currency_symbol_extract_expr(quoted)
    nullish = _nullish_predicate(quoted, null_tokens)

    rows = conn.execute(
        "SELECT symbol, COUNT(*) AS c FROM ("
        f"SELECT {symbol_expr} AS symbol FROM raw_input WHERE NOT ({nullish})"
        ") t WHERE symbol IS NOT NULL GROUP BY symbol ORDER BY c DESC, symbol ASC"
    ).fetchall()
    distribution = {str(symbol): int(count) for symbol, count in rows}

    dominant_symbol = None
    dominant_count = 0
    if distribution:
        dominant_symbol, dominant_count = max(distribution.items(), key=lambda item: item[1])

    dominant_symbol_ratio = 1.0 if non_null_count <= 0 else (dominant_count / non_null_count)
    has_mixed = len(distribution) > 1

    return CurrencyColumnProfile(
        symbol_distribution=distribution,
        dominant_symbol=dominant_symbol,
        dominant_symbol_ratio=dominant_symbol_ratio,
        non_nullish_count=non_null_count,
        has_mixed_symbols=has_mixed,
    )


def _nullish_predicate(value_expr: str, null_tokens: tuple[str, ...]) -> str:
    base = f"NULLIF(TRIM(CAST({value_expr} AS VARCHAR)), '')"
    normalized_tokens = sorted({token.strip().lower() for token in null_tokens if token.strip()})
    if not normalized_tokens:
        return f"{base} IS NULL"
    in_clause = ", ".join(quote_string(token) for token in normalized_tokens)
    return f"{base} IS NULL OR LOWER(TRIM(CAST({value_expr} AS VARCHAR))) IN ({in_clause})"
