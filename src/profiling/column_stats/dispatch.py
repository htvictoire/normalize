"""Batch dispatch from column configs to column profiles."""

from __future__ import annotations

from duckdb import DuckDBPyConnection

from shared.db.sql import quote_identifier
from shared.models.column import (
    BooleanColumnConfig,
    CategoricalColumnConfig,
    ColumnConfig,
    CountryCodeColumnConfig,
    CurrencyCodeColumnConfig,
    DateColumnConfig,
    DateTimeColumnConfig,
    DecimalColumnConfig,
    EmailColumnConfig,
    IdentifierColumnConfig,
    IntegerColumnConfig,
    IpAddressColumnConfig,
    LanguageCodeColumnConfig,
    PercentageColumnConfig,
    PhoneColumnConfig,
    SignedColumnConfig,
    StringColumnConfig,
    TimeColumnConfig,
    UrlColumnConfig,
    has_monetary_symbol,
)
from shared.models.profiling import ColumnCounts, ColumnProfile
from shared.parsing.normalizer import build_value_candidate_expr

from profiling.column_stats.ai_only import (
    AiOnlyBatchEntry,
    compute_ai_only_column_profiles_batch,
)
from profiling.column_stats.boolean import (
    BooleanBatchEntry,
    compute_boolean_column_profiles_batch,
    make_boolean_batch_entry,
)
from profiling.column_stats.code import CodeBatchEntry, compute_code_column_profiles_batch
from profiling.column_stats.common import compute_decimal_parse_stats_batch
from profiling.column_stats.date import (
    DateBatchEntry,
    DateTimeBatchEntry,
    TimeBatchEntry,
    compute_date_column_profiles_batch,
    compute_datetime_column_profiles_batch,
    compute_time_column_profiles_batch,
)
from profiling.column_stats.decimal import (
    DecimalStatsBatchEntry,
    compute_decimal_stats_profiles_batch,
)
from profiling.column_stats.identifier import (
    IdentifierBatchEntry,
    compute_identifier_column_profiles_batch,
)
from profiling.column_stats.integer import IntegerBatchEntry, compute_integer_column_profiles_batch
from profiling.column_stats.string import StringBatchEntry, compute_string_column_profiles_batch
from profiling.column_stats.symbol import (
    SymbolColumnEntry,
    compute_symbol_column_profile,
    compute_symbol_metrics_batch,
)


def compute_column_profiles(
    conn: DuckDBPyConnection,
    columns: list[str],
    column_config: dict[str, ColumnConfig],
    null_tokens: tuple[str, ...],
    counts_by_name: dict[str, ColumnCounts],
) -> dict[str, ColumnProfile]:
    """Compute profiles for all columns, grouping same-type columns into batched queries.

    Currency and accounting columns use one scan for parse stats and one grouped query
    for monetary formatting metrics across all symbol-bearing columns. We keep one
    mixed symbol-metrics batch even though currency and accounting now have
    separate metric types, because splitting them would add another grouped scan.
    """
    string_batch: list[StringBatchEntry] = []
    identifier_batch: list[IdentifierBatchEntry] = []
    boolean_batch: list[BooleanBatchEntry] = []
    date_batch: list[DateBatchEntry] = []
    datetime_batch: list[DateTimeBatchEntry] = []
    time_batch: list[TimeBatchEntry] = []
    code_batch: list[CodeBatchEntry] = []
    ai_only_batch: list[AiOnlyBatchEntry] = []
    integer_batch: list[IntegerBatchEntry] = []
    decimal_stats_batch: list[DecimalStatsBatchEntry] = []
    symbol_columns: list[SymbolColumnEntry] = []

    for col_name in columns:
        config = column_config[col_name]
        counts = counts_by_name[col_name]

        if isinstance(config, StringColumnConfig):
            string_batch.append(StringBatchEntry(col_name, counts))
        elif isinstance(config, IdentifierColumnConfig):
            identifier_batch.append(IdentifierBatchEntry(col_name, counts))
        elif isinstance(config, BooleanColumnConfig):
            boolean_batch.append(make_boolean_batch_entry(col_name, config, counts))
        elif isinstance(config, DateColumnConfig):
            date_batch.append(DateBatchEntry(col_name, config, counts))
        elif isinstance(config, DateTimeColumnConfig):
            datetime_batch.append(DateTimeBatchEntry(col_name, config, counts))
        elif isinstance(config, TimeColumnConfig):
            time_batch.append(TimeBatchEntry(col_name, config, counts))
        elif isinstance(
            config,
            (CountryCodeColumnConfig, CurrencyCodeColumnConfig, LanguageCodeColumnConfig),
        ):
            code_batch.append(CodeBatchEntry(col_name, config, counts))
        elif isinstance(
            config,
            (
                CategoricalColumnConfig,
                EmailColumnConfig,
                UrlColumnConfig,
                IpAddressColumnConfig,
                PhoneColumnConfig,
            ),
        ):
            ai_only_batch.append(AiOnlyBatchEntry(col_name, config, counts))
        else:
            raw_col = f"TRIM(CAST({quote_identifier(col_name)} AS VARCHAR))"
            value_expr = build_value_candidate_expr(raw_col, config)
            if isinstance(config, IntegerColumnConfig):
                integer_batch.append(IntegerBatchEntry(col_name, config, counts, value_expr))
            elif has_monetary_symbol(config):
                symbol_columns.append(SymbolColumnEntry(col_name, config, counts, value_expr))
            elif isinstance(
                config, (DecimalColumnConfig, PercentageColumnConfig, SignedColumnConfig)
            ):
                decimal_stats_batch.append(
                    DecimalStatsBatchEntry(col_name, config, counts, value_expr)
                )
            else:
                raise TypeError(f"Unsupported column config: {type(config).__name__}")

    profiles: dict[str, ColumnProfile] = {}
    profiles |= compute_string_column_profiles_batch(conn, string_batch, null_tokens)
    profiles |= compute_identifier_column_profiles_batch(conn, identifier_batch, null_tokens)
    profiles |= compute_boolean_column_profiles_batch(conn, boolean_batch, null_tokens)
    profiles |= compute_date_column_profiles_batch(conn, date_batch, null_tokens)
    profiles |= compute_datetime_column_profiles_batch(conn, datetime_batch, null_tokens)
    profiles |= compute_time_column_profiles_batch(conn, time_batch, null_tokens)
    profiles |= compute_code_column_profiles_batch(conn, code_batch, null_tokens)
    profiles |= compute_ai_only_column_profiles_batch(conn, ai_only_batch, null_tokens)
    profiles |= compute_integer_column_profiles_batch(conn, integer_batch, null_tokens)
    profiles |= compute_decimal_stats_profiles_batch(conn, decimal_stats_batch, null_tokens)

    symbol_parse_stats = compute_decimal_parse_stats_batch(conn, symbol_columns, null_tokens)
    symbol_metrics = compute_symbol_metrics_batch(conn, symbol_columns, null_tokens)
    for entry in symbol_columns:
        profiles[entry.column_name] = compute_symbol_column_profile(
            entry.config,
            entry.counts,
            symbol_parse_stats[entry.column_name],
            symbol_metrics[entry.column_name],
        )

    return profiles
