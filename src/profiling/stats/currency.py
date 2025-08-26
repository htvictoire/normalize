"""Currency profiling stats."""

from __future__ import annotations

from duckdb import DuckDBPyConnection

from shared.db.sql import nullish_predicate, quote_identifier
from shared.models.profiling import ColumnCounts, CurrencyColumnProfile
from shared.utils.currency import build_currency_symbol_extract_expr


def compute_currency_column_profile(
    conn: DuckDBPyConnection,
    *,
    column_name: str,
    null_tokens: tuple[str, ...],
    counts: ColumnCounts,
) -> CurrencyColumnProfile:
    """Compute symbol distribution and dominant symbol metrics."""
    quoted = quote_identifier(column_name)
    symbol_expr = build_currency_symbol_extract_expr(quoted)
    nullish = nullish_predicate(quoted, null_tokens)

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

    non_nullish = counts.non_nullish_count
    dominant_symbol_ratio = 1.0 if non_nullish <= 0 else (dominant_count / non_nullish)

    return CurrencyColumnProfile(
        symbol_distribution=distribution,
        dominant_symbol=dominant_symbol,
        dominant_symbol_ratio=dominant_symbol_ratio,
        has_mixed_symbols=len(distribution) > 1,
    )
