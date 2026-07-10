"""Standardized-code profiling stats."""

from __future__ import annotations

from dataclasses import dataclass

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.aggregates import fetch_aggregate_int_row, safe_ratio
from shared.db.sql import nullish_predicate, quote_identifier
from shared.models.column import (
    CountryCodeColumnConfig,
    CurrencyCodeColumnConfig,
    LanguageCodeColumnConfig,
)
from shared.models.profiling import (
    ColumnCounts,
    ColumnProfile,
    profile_class_for_config,
)
from shared.parsing.iso_codes import country_codes, currency_codes, language_codes, sql_in_list

type CodeConfig = CountryCodeColumnConfig | CurrencyCodeColumnConfig | LanguageCodeColumnConfig


@dataclass(frozen=True)
class CodeBatchEntry:
    column_name: str
    config: CodeConfig
    counts: ColumnCounts


def _code_expr(quoted_column: str, config: CodeConfig) -> tuple[str, frozenset[str]]:
    if isinstance(config, CountryCodeColumnConfig):
        return f"UPPER(TRIM(CAST({quoted_column} AS VARCHAR)))", country_codes(
            config.code_format
        )
    if isinstance(config, CurrencyCodeColumnConfig):
        return f"UPPER(TRIM(CAST({quoted_column} AS VARCHAR)))", currency_codes()
    return f"LOWER(TRIM(CAST({quoted_column} AS VARCHAR)))", language_codes(
        config.code_format
    )


def _profile(config: CodeConfig, valid_count: int, non_nullish: int) -> ColumnProfile:
    invalid_count = non_nullish - valid_count
    valid_ratio = safe_ratio(valid_count, non_nullish)
    profile_cls = profile_class_for_config(config)
    return profile_cls(
        valid_count=valid_count,
        invalid_count=invalid_count,
        valid_ratio=valid_ratio,
    )


def compute_code_column_profiles_batch(
    conn: DuckDBPyConnection,
    batch: list[CodeBatchEntry],
    null_tokens: tuple[str, ...],
) -> dict[str, ColumnProfile]:
    """Count valid standardized-code values for all code columns in one table scan."""
    if not batch:
        return {}

    exprs: list[str] = []
    for entry in batch:
        quoted = quote_identifier(entry.column_name)
        nullish = nullish_predicate(quoted, null_tokens)
        code_expr, allowed_codes = _code_expr(quoted, entry.config)
        exprs.append(
            f"COUNT(*) FILTER (WHERE NOT ({nullish}) "
            f"AND {code_expr} IN ({sql_in_list(allowed_codes)}))"
        )

    row = fetch_aggregate_int_row(conn, f"SELECT {', '.join(exprs)} FROM {RAW_INPUT_TABLE_NAME}")

    profiles: dict[str, ColumnProfile] = {}
    for entry, valid_count in zip(batch, row, strict=True):
        non_nullish = entry.counts.non_nullish_count
        profiles[entry.column_name] = _profile(entry.config, valid_count, non_nullish)
    return profiles
