"""Symbol-family profiling stats — currency and accounting types."""

from __future__ import annotations

from dataclasses import dataclass

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.sql import nullish_predicate, quote_identifier
from shared.models.column import DecimalFamilyColumnConfig
from shared.models.profiling import ColumnCounts
from shared.parsing.currency import build_currency_symbol_extract_expr

from profiling.column_stats.decimal import decimal_parse_stats


@dataclass(frozen=True)
class SymbolFamilyStats:
    """Combined symbol distribution and parse-match stats for currency/accounting columns."""

    symbol_distribution: dict[str, int]
    dominant_symbol: str | None
    dominant_symbol_ratio: float
    has_mixed_symbols: bool
    parse_match_count: int
    parse_match_ratio: float
    swapped_match_count: int
    swapped_match_ratio: float
    separator_mismatch_detected: bool


def compute_symbol_distribution(
    conn: DuckDBPyConnection,
    column_name: str,
    null_tokens: tuple[str, ...],
) -> dict[str, int]:
    """Return {symbol: count} ordered by count DESC, symbol ASC for a symbol-bearing column.

    The dict is insertion-ordered: the first entry is always the dominant symbol.
    """
    quoted = quote_identifier(column_name)
    symbol_expr = build_currency_symbol_extract_expr(quoted)
    nullish = nullish_predicate(quoted, null_tokens)

    rows = conn.execute(
        "SELECT symbol, COUNT(*) AS c FROM ("
        f"SELECT {symbol_expr} AS symbol FROM {RAW_INPUT_TABLE_NAME} WHERE NOT ({nullish})"
        ") t WHERE symbol IS NOT NULL GROUP BY symbol ORDER BY c DESC, symbol ASC"
    ).fetchall()
    return {str(symbol): int(count) for symbol, count in rows}


def compute_symbol_family_stats(
    conn: DuckDBPyConnection,
    column_name: str,
    config: DecimalFamilyColumnConfig,
    null_tokens: tuple[str, ...],
    counts: ColumnCounts,
    normalized_value_expr: str,
) -> SymbolFamilyStats:
    """Compute symbol distribution and decimal parse stats for currency/accounting columns."""
    distribution = compute_symbol_distribution(conn, column_name, null_tokens)
    dominant_symbol: str | None = next(iter(distribution), None)
    dominant_count = distribution[dominant_symbol] if dominant_symbol is not None else 0
    non_nullish = counts.non_nullish_count
    dominant_symbol_ratio = 1.0 if non_nullish <= 0 else (dominant_count / non_nullish)
    stats = decimal_parse_stats(
        conn,
        column_name=column_name,
        config=config,
        null_tokens=null_tokens,
        counts=counts,
        normalized_value_expr=normalized_value_expr,
    )
    return SymbolFamilyStats(
        symbol_distribution=distribution,
        dominant_symbol=dominant_symbol,
        dominant_symbol_ratio=dominant_symbol_ratio,
        has_mixed_symbols=len(distribution) > 1,
        parse_match_count=stats.parse_match_count,
        parse_match_ratio=stats.parse_match_ratio,
        swapped_match_count=stats.swapped_match_count,
        swapped_match_ratio=stats.swapped_match_ratio,
        separator_mismatch_detected=stats.swapped_match_count > stats.parse_match_count,
    )
