"""Numeric profiling stats — one compute function per numeric config type."""

from __future__ import annotations

from duckdb import DuckDBPyConnection

from conversion.stages.cell_normalization.transforms.numeric import (
    decimal_pattern_regex,
    integer_pattern_regex,
)
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


def compute_integer_column_profile(
    conn: DuckDBPyConnection,
    *,
    column_name: str,
    config: IntegerColumnConfig,
    null_tokens: tuple[str, ...],
    counts: ColumnCounts,
    normalized_value_expr: str,
) -> IntegerColumnProfile:
    """Count values that match the declared integer format."""
    quoted = quote_identifier(column_name)
    match_value = normalized_value_expr
    nullish = nullish_predicate(quoted, null_tokens)
    non_nullish = counts.non_nullish_count

    pattern = integer_pattern_regex(
        thousand_separator=config.thousand_separator,
        grouping_style=config.grouping_style,
    )
    parse_match_count = execute_scalar(
        conn,
        f"SELECT COUNT(*) FROM raw_input WHERE NOT ({nullish}) "
        f"AND REGEXP_FULL_MATCH({match_value}, {quote_string(pattern)})",
    )
    parse_match_ratio = 1.0 if non_nullish <= 0 else (parse_match_count / non_nullish)
    return IntegerColumnProfile(
        parse_match_count=parse_match_count,
        parse_match_ratio=parse_match_ratio,
    )


def compute_decimal_column_profile(
    conn: DuckDBPyConnection,
    *,
    column_name: str,
    config: DecimalColumnConfig,
    null_tokens: tuple[str, ...],
    counts: ColumnCounts,
    normalized_value_expr: str,
) -> DecimalColumnProfile:
    """Count values matching the declared decimal format; detect separator swaps."""
    pm, pmr, sm, smr = decimal_parse_stats(
        conn,
        column_name=column_name,
        config=config,
        null_tokens=null_tokens,
        counts=counts,
        normalized_value_expr=normalized_value_expr,
    )
    return DecimalColumnProfile(
        parse_match_count=pm,
        parse_match_ratio=pmr,
        swapped_match_count=sm,
        swapped_match_ratio=smr,
        separator_mismatch_detected=sm > pm,
    )


def compute_percentage_column_profile(
    conn: DuckDBPyConnection,
    *,
    column_name: str,
    config: PercentageColumnConfig,
    null_tokens: tuple[str, ...],
    counts: ColumnCounts,
    normalized_value_expr: str,
) -> PercentageColumnProfile:
    """Count values matching the declared percentage format; detect separator swaps."""
    pm, pmr, sm, smr = decimal_parse_stats(
        conn,
        column_name=column_name,
        config=config,
        null_tokens=null_tokens,
        counts=counts,
        normalized_value_expr=normalized_value_expr,
    )
    return PercentageColumnProfile(
        parse_match_count=pm,
        parse_match_ratio=pmr,
        swapped_match_count=sm,
        swapped_match_ratio=smr,
        separator_mismatch_detected=sm > pm,
    )


def compute_signed_column_profile(
    conn: DuckDBPyConnection,
    *,
    column_name: str,
    config: SignedColumnConfig,
    null_tokens: tuple[str, ...],
    counts: ColumnCounts,
    normalized_value_expr: str,
) -> SignedColumnProfile:
    """Count values matching the declared signed format; detect separator swaps."""
    pm, pmr, sm, smr = decimal_parse_stats(
        conn,
        column_name=column_name,
        config=config,
        null_tokens=null_tokens,
        counts=counts,
        normalized_value_expr=normalized_value_expr,
    )
    return SignedColumnProfile(
        parse_match_count=pm,
        parse_match_ratio=pmr,
        swapped_match_count=sm,
        swapped_match_ratio=smr,
        separator_mismatch_detected=sm > pm,
    )


def decimal_parse_stats(
    conn: DuckDBPyConnection,
    *,
    column_name: str,
    config: DecimalFamilyColumnConfig,
    null_tokens: tuple[str, ...],
    counts: ColumnCounts,
    normalized_value_expr: str,
) -> tuple[int, float, int, float]:
    """Return (parse_match_count, parse_match_ratio, swapped_match_count, swapped_match_ratio).

    Shared by all decimal-family types: decimal, percentage, signed, currency, accounting.
    """
    quoted = quote_identifier(column_name)
    match_value = normalized_value_expr
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
        f"SELECT COUNT(*) FROM raw_input WHERE NOT ({nullish}) "
        f"AND REGEXP_FULL_MATCH({match_value}, {quote_string(declared_pattern)})",
    )
    swapped_match_count = execute_scalar(
        conn,
        f"SELECT COUNT(*) FROM raw_input WHERE NOT ({nullish}) "
        f"AND REGEXP_FULL_MATCH({match_value}, {quote_string(swapped_pattern)})",
    )

    parse_match_ratio = 1.0 if non_nullish <= 0 else (parse_match_count / non_nullish)
    swapped_match_ratio = 1.0 if non_nullish <= 0 else (swapped_match_count / non_nullish)
    return parse_match_count, parse_match_ratio, swapped_match_count, swapped_match_ratio
