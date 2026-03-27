"""Single-entry dispatch from ColumnConfig to its column profile."""

from __future__ import annotations

from duckdb import DuckDBPyConnection

from shared.db.sql import quote_identifier
from shared.models.column import (
    AccountingColumnConfig,
    BooleanColumnConfig,
    ColumnConfig,
    CurrencyColumnConfig,
    DateColumnConfig,
    DecimalColumnConfig,
    IntegerColumnConfig,
    PercentageColumnConfig,
    SignedColumnConfig,
    StringColumnConfig,
)
from shared.models.profiling import ColumnCounts, ColumnProfile
from shared.parsing.normalizer import build_value_candidate_expr

from profiling.column_stats.accounting import compute_accounting_column_profile
from profiling.column_stats.boolean import compute_boolean_column_profile
from profiling.column_stats.currency import compute_currency_column_profile
from profiling.column_stats.date import compute_date_column_profile
from profiling.column_stats.numeric import (
    compute_decimal_column_profile,
    compute_integer_column_profile,
    compute_percentage_column_profile,
    compute_signed_column_profile,
)
from profiling.column_stats.string import compute_string_column_profile


def compute_column_profile(  # noqa: PLR0911
    conn: DuckDBPyConnection,
    column_name: str,
    config: ColumnConfig,
    null_tokens: tuple[str, ...],
    counts: ColumnCounts,
) -> ColumnProfile:
    """Dispatch to the correct per-type profiler and return the column profile."""
    # Types that need no value preprocessing — return before building the candidate expr.
    if isinstance(config, StringColumnConfig):
        return compute_string_column_profile(
            conn, column_name=column_name, null_tokens=null_tokens, counts=counts
        )
    if isinstance(config, BooleanColumnConfig):
        return compute_boolean_column_profile(
            conn,
            column_name=column_name,
            true_tokens=config.true_tokens,
            false_tokens=config.false_tokens,
            null_tokens=null_tokens,
            counts=counts,
        )
    if isinstance(config, DateColumnConfig):
        return compute_date_column_profile(
            conn,
            column_name=column_name,
            date_format=config.date_format,
            null_tokens=null_tokens,
            counts=counts,
        )

    # All remaining types are numeric — build the preprocessed value expression once.
    raw_col = f"TRIM(CAST({quote_identifier(column_name)} AS VARCHAR))"
    candidate = build_value_candidate_expr(raw_col, config)

    if isinstance(config, IntegerColumnConfig):
        return compute_integer_column_profile(
            conn,
            column_name=column_name,
            config=config,
            null_tokens=null_tokens,
            counts=counts,
            normalized_value_expr=candidate,
        )
    if isinstance(config, DecimalColumnConfig):
        return compute_decimal_column_profile(
            conn,
            column_name=column_name,
            config=config,
            null_tokens=null_tokens,
            counts=counts,
            normalized_value_expr=candidate,
        )
    if isinstance(config, PercentageColumnConfig):
        return compute_percentage_column_profile(
            conn,
            column_name=column_name,
            config=config,
            null_tokens=null_tokens,
            counts=counts,
            normalized_value_expr=candidate,
        )
    if isinstance(config, SignedColumnConfig):
        return compute_signed_column_profile(
            conn,
            column_name=column_name,
            config=config,
            null_tokens=null_tokens,
            counts=counts,
            normalized_value_expr=candidate,
        )
    if isinstance(config, CurrencyColumnConfig):
        return compute_currency_column_profile(
            conn,
            column_name=column_name,
            config=config,
            null_tokens=null_tokens,
            counts=counts,
            normalized_value_expr=candidate,
        )
    if isinstance(config, AccountingColumnConfig):
        return compute_accounting_column_profile(
            conn,
            column_name=column_name,
            config=config,
            null_tokens=null_tokens,
            counts=counts,
            normalized_value_expr=candidate,
        )
    raise TypeError(f"Unsupported column config: {type(config).__name__}")
