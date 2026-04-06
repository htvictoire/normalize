"""Decimal-family profiling stats — decimal, percentage, and signed types."""

from __future__ import annotations

from dataclasses import dataclass

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.sql import execute_scalar, nullish_predicate, quote_identifier, quote_string
from shared.models.column import (
    DecimalColumnConfig,
    DecimalFamilyColumnConfig,
    PercentageColumnConfig,
    SignedColumnConfig,
)
from shared.models.profiling import (
    ColumnCounts,
    DecimalColumnProfile,
    PercentageColumnProfile,
    SignedColumnProfile,
)
from shared.parsing.numeric import decimal_pattern_regex


@dataclass(frozen=True)
class DecimalParseStats:
    """Parse-match and swapped-separator counts for any decimal-family column."""

    parse_match_count: int
    parse_match_ratio: float
    swapped_match_count: int
    swapped_match_ratio: float


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

    row = conn.execute(
        f"SELECT"
        f" COUNT(*) FILTER (WHERE REGEXP_FULL_MATCH({normalized_value_expr}, {quote_string(declared_pattern)})),"
        f" COUNT(*) FILTER (WHERE REGEXP_FULL_MATCH({normalized_value_expr}, {quote_string(swapped_pattern)}))"
        f" FROM {RAW_INPUT_TABLE_NAME} WHERE NOT ({nullish})"
    ).fetchone()
    parse_match_count: int = row[0]  # type: ignore[index]
    swapped_match_count: int = row[1]  # type: ignore[index]

    parse_match_ratio = 1.0 if non_nullish <= 0 else (parse_match_count / non_nullish)
    swapped_match_ratio = 1.0 if non_nullish <= 0 else (swapped_match_count / non_nullish)
    return DecimalParseStats(
        parse_match_count=parse_match_count,
        parse_match_ratio=parse_match_ratio,
        swapped_match_count=swapped_match_count,
        swapped_match_ratio=swapped_match_ratio,
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
