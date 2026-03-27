"""Numeric profiling stats — one compute function per numeric config type."""

from __future__ import annotations

from dataclasses import dataclass

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.sql import execute_scalar, nullish_predicate, quote_identifier, quote_string
from shared.models.column import (
    DecimalColumnConfig,
    DecimalFamilyColumnConfig,
    IntegerColumnConfig,
    PercentageColumnConfig,
    SignedColumnConfig,
)
from shared.models.profiling import (
    ColumnCounts,
    DecimalColumnProfile,
    IntegerColumnProfile,
    PercentageColumnProfile,
    SignedColumnProfile,
)
from shared.parsing.currency import build_currency_symbol_extract_expr

from conversion.stages.cell_normalization.transforms.numeric import (
    decimal_pattern_regex,
    integer_pattern_regex,
)


@dataclass(frozen=True)
class DecimalParseStats:
    """Parse-match and swapped-separator counts for any decimal-family column."""

    parse_match_count: int
    parse_match_ratio: float
    swapped_match_count: int
    swapped_match_ratio: float


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


def compute_integer_column_profile(
    conn: DuckDBPyConnection,
    column_name: str,
    config: IntegerColumnConfig,
    null_tokens: tuple[str, ...],
    counts: ColumnCounts,
    normalized_value_expr: str,
) -> IntegerColumnProfile:
    """Count values that match the declared integer format."""
    quoted = quote_identifier(column_name)
    nullish = nullish_predicate(quoted, null_tokens)
    non_nullish = counts.non_nullish_count

    pattern = integer_pattern_regex(
        thousand_separator=config.thousand_separator,
        grouping_style=config.grouping_style,
    )
    parse_match_count = execute_scalar(
        conn,
        f"SELECT COUNT(*) FROM {RAW_INPUT_TABLE_NAME} WHERE NOT ({nullish}) "
        f"AND REGEXP_FULL_MATCH({normalized_value_expr}, {quote_string(pattern)})",
    )
    parse_match_ratio = 1.0 if non_nullish <= 0 else (parse_match_count / non_nullish)
    return IntegerColumnProfile(
        parse_match_count=parse_match_count,
        parse_match_ratio=parse_match_ratio,
    )


def compute_decimal_column_profile(
    conn: DuckDBPyConnection,
    column_name: str,
    config: DecimalColumnConfig,
    null_tokens: tuple[str, ...],
    counts: ColumnCounts,
    normalized_value_expr: str,
) -> DecimalColumnProfile:
    """Count values matching the declared decimal format; detect separator swaps."""
    stats = decimal_parse_stats(
        conn,
        column_name=column_name,
        config=config,
        null_tokens=null_tokens,
        counts=counts,
        normalized_value_expr=normalized_value_expr,
    )
    return DecimalColumnProfile(
        parse_match_count=stats.parse_match_count,
        parse_match_ratio=stats.parse_match_ratio,
        swapped_match_count=stats.swapped_match_count,
        swapped_match_ratio=stats.swapped_match_ratio,
        separator_mismatch_detected=stats.swapped_match_count > stats.parse_match_count,
    )


def compute_percentage_column_profile(
    conn: DuckDBPyConnection,
    column_name: str,
    config: PercentageColumnConfig,
    null_tokens: tuple[str, ...],
    counts: ColumnCounts,
    normalized_value_expr: str,
) -> PercentageColumnProfile:
    """Count values matching the declared percentage format; detect separator swaps."""
    stats = decimal_parse_stats(
        conn,
        column_name=column_name,
        config=config,
        null_tokens=null_tokens,
        counts=counts,
        normalized_value_expr=normalized_value_expr,
    )
    return PercentageColumnProfile(
        parse_match_count=stats.parse_match_count,
        parse_match_ratio=stats.parse_match_ratio,
        swapped_match_count=stats.swapped_match_count,
        swapped_match_ratio=stats.swapped_match_ratio,
        separator_mismatch_detected=stats.swapped_match_count > stats.parse_match_count,
    )


def compute_signed_column_profile(
    conn: DuckDBPyConnection,
    column_name: str,
    config: SignedColumnConfig,
    null_tokens: tuple[str, ...],
    counts: ColumnCounts,
    normalized_value_expr: str,
) -> SignedColumnProfile:
    """Count values matching the declared signed format; detect separator swaps."""
    stats = decimal_parse_stats(
        conn,
        column_name=column_name,
        config=config,
        null_tokens=null_tokens,
        counts=counts,
        normalized_value_expr=normalized_value_expr,
    )
    return SignedColumnProfile(
        parse_match_count=stats.parse_match_count,
        parse_match_ratio=stats.parse_match_ratio,
        swapped_match_count=stats.swapped_match_count,
        swapped_match_ratio=stats.swapped_match_ratio,
        separator_mismatch_detected=stats.swapped_match_count > stats.parse_match_count,
    )


def decimal_parse_stats(
    conn: DuckDBPyConnection,
    column_name: str,
    config: DecimalFamilyColumnConfig,
    null_tokens: tuple[str, ...],
    counts: ColumnCounts,
    normalized_value_expr: str,
) -> DecimalParseStats:
    """Return parse-match and swapped-separator counts for a decimal-family column.

    Shared by all decimal-family types: decimal, percentage, signed, currency, accounting.
    """
    quoted = quote_identifier(column_name)
    nullish = nullish_predicate(quoted, null_tokens)
    non_nullish = counts.non_nullish_count

    declared_pattern = decimal_pattern_regex(
        decimal_separator=config.decimal_separator,
        thousand_separator=config.thousand_separator,
        grouping_style=config.grouping_style,
        allow_leading_decimal_point=config.allow_leading_decimal_point,
    )
    swapped_pattern = decimal_pattern_regex(
        decimal_separator=config.thousand_separator,
        thousand_separator=config.decimal_separator,
        grouping_style=config.grouping_style,
        allow_leading_decimal_point=config.allow_leading_decimal_point,
    )

    parse_match_count = execute_scalar(
        conn,
        f"SELECT COUNT(*) FROM {RAW_INPUT_TABLE_NAME} WHERE NOT ({nullish}) "
        f"AND REGEXP_FULL_MATCH({normalized_value_expr}, {quote_string(declared_pattern)})",
    )
    swapped_match_count = execute_scalar(
        conn,
        f"SELECT COUNT(*) FROM {RAW_INPUT_TABLE_NAME} WHERE NOT ({nullish}) "
        f"AND REGEXP_FULL_MATCH({normalized_value_expr}, {quote_string(swapped_pattern)})",
    )

    parse_match_ratio = 1.0 if non_nullish <= 0 else (parse_match_count / non_nullish)
    swapped_match_ratio = 1.0 if non_nullish <= 0 else (swapped_match_count / non_nullish)
    return DecimalParseStats(
        parse_match_count=parse_match_count,
        parse_match_ratio=parse_match_ratio,
        swapped_match_count=swapped_match_count,
        swapped_match_ratio=swapped_match_ratio,
    )


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
