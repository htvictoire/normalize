"""Currency profiling stats."""

from __future__ import annotations

from duckdb import DuckDBPyConnection

from shared.models.column import CurrencyColumnConfig
from shared.models.profiling import ColumnCounts, CurrencyColumnProfile

from profiling.column_stats.numeric import compute_symbol_family_stats


def compute_currency_column_profile(
    conn: DuckDBPyConnection,
    column_name: str,
    config: CurrencyColumnConfig,
    null_tokens: tuple[str, ...],
    counts: ColumnCounts,
    normalized_value_expr: str,
) -> CurrencyColumnProfile:
    """Compute symbol distribution and parse match metrics for a currency column."""
    stats = compute_symbol_family_stats(
        conn, column_name, config, null_tokens, counts, normalized_value_expr
    )
    return CurrencyColumnProfile(
        symbol_distribution=stats.symbol_distribution,
        dominant_symbol=stats.dominant_symbol,
        dominant_symbol_ratio=stats.dominant_symbol_ratio,
        has_mixed_symbols=stats.has_mixed_symbols,
        parse_match_count=stats.parse_match_count,
        parse_match_ratio=stats.parse_match_ratio,
        swapped_match_count=stats.swapped_match_count,
        swapped_match_ratio=stats.swapped_match_ratio,
        separator_mismatch_detected=stats.separator_mismatch_detected,
    )
