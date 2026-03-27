"""Accounting profiling stats."""

from __future__ import annotations

from duckdb import DuckDBPyConnection

from profiling.column_stats.numeric import decimal_parse_stats
from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.sql import nullish_predicate, quote_identifier
from shared.models.column import AccountingColumnConfig
from shared.models.profiling import AccountingColumnProfile, ColumnCounts
from shared.parsing.currency import build_currency_symbol_extract_expr


def compute_accounting_column_profile(
    conn: DuckDBPyConnection,
    *,
    column_name: str,
    config: AccountingColumnConfig,
    null_tokens: tuple[str, ...],
    counts: ColumnCounts,
    normalized_value_expr: str,
) -> AccountingColumnProfile:
    """Compute symbol distribution and parse match metrics for an accounting column."""
    quoted = quote_identifier(column_name)
    symbol_expr = build_currency_symbol_extract_expr(quoted)
    nullish = nullish_predicate(quoted, null_tokens)

    rows = conn.execute(
        "SELECT symbol, COUNT(*) AS c FROM ("
        f"SELECT {symbol_expr} AS symbol FROM {RAW_INPUT_TABLE_NAME} WHERE NOT ({nullish})"
        ") t WHERE symbol IS NOT NULL GROUP BY symbol ORDER BY c DESC, symbol ASC"
    ).fetchall()
    distribution = {str(symbol): int(count) for symbol, count in rows}

    dominant_symbol = None
    dominant_count = 0
    if distribution:
        dominant_symbol, dominant_count = max(distribution.items(), key=lambda item: item[1])

    non_nullish = counts.non_nullish_count
    dominant_symbol_ratio = 1.0 if non_nullish <= 0 else (dominant_count / non_nullish)

    pm, pmr, sm, smr = decimal_parse_stats(
        conn,
        column_name=column_name,
        config=config,
        null_tokens=null_tokens,
        counts=counts,
        normalized_value_expr=normalized_value_expr,
    )

    return AccountingColumnProfile(
        symbol_distribution=distribution,
        dominant_symbol=dominant_symbol,
        dominant_symbol_ratio=dominant_symbol_ratio,
        has_mixed_symbols=len(distribution) > 1,
        parse_match_count=pm,
        parse_match_ratio=pmr,
        swapped_match_count=sm,
        swapped_match_ratio=smr,
        separator_mismatch_detected=sm > pm,
    )
