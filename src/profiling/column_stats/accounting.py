"""Accounting profiling stats."""

from __future__ import annotations

from duckdb import DuckDBPyConnection

from shared.models.column import AccountingColumnConfig
from shared.models.profiling import AccountingColumnProfile, ColumnCounts

from profiling.column_stats.numeric import compute_symbol_distribution, decimal_parse_stats


def compute_accounting_column_profile(
    conn: DuckDBPyConnection,
    column_name: str,
    config: AccountingColumnConfig,
    null_tokens: tuple[str, ...],
    counts: ColumnCounts,
    normalized_value_expr: str,
) -> AccountingColumnProfile:
    """Compute symbol distribution and parse match metrics for an accounting column."""
    distribution = compute_symbol_distribution(conn, column_name=column_name, null_tokens=null_tokens)

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

    return AccountingColumnProfile(
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
