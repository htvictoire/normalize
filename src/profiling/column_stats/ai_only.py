"""Profiling stats for confirmed AI-only configs."""

from __future__ import annotations

from dataclasses import dataclass

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.aggregates import fetch_aggregate_int_row, safe_ratio
from shared.db.sql import nullish_predicate, quote_identifier
from shared.models.column import (
    CategoricalColumnConfig,
    EmailColumnConfig,
    IpAddressColumnConfig,
    PhoneColumnConfig,
    UrlColumnConfig,
)
from shared.models.profiling import (
    ColumnCounts,
    ColumnProfile,
    profile_class_for_config,
)
from shared.parsing.iso_codes import sql_in_list
from shared.parsing.structured_strings import (
    EMAIL_PATTERN,
    PHONE_PATTERN,
    URL_PATTERN,
    ip_address_pattern,
    lowercase_email_expr,
    phone_e164_candidate_expr,
    regex_full_match_expr,
    trim_cast_expr,
)

type AiOnlyProfileConfig = (
    CategoricalColumnConfig
    | EmailColumnConfig
    | UrlColumnConfig
    | IpAddressColumnConfig
    | PhoneColumnConfig
)


@dataclass(frozen=True)
class AiOnlyBatchEntry:
    column_name: str
    config: AiOnlyProfileConfig
    counts: ColumnCounts


def _valid_predicate(quoted_column: str, config: AiOnlyProfileConfig) -> str:
    trimmed = trim_cast_expr(quoted_column)
    if isinstance(config, CategoricalColumnConfig):
        allowed_values = frozenset(value.strip().lower() for value in config.canonical_values)
        if not allowed_values:
            return "FALSE"
        return f"LOWER({trimmed}) IN ({sql_in_list(allowed_values)})"
    if isinstance(config, EmailColumnConfig):
        return regex_full_match_expr(lowercase_email_expr(quoted_column), EMAIL_PATTERN)
    if isinstance(config, UrlColumnConfig):
        return regex_full_match_expr(trimmed, URL_PATTERN)
    if isinstance(config, IpAddressColumnConfig):
        return regex_full_match_expr(trimmed, ip_address_pattern(config.version))
    return regex_full_match_expr(phone_e164_candidate_expr(quoted_column), PHONE_PATTERN)


def _profile(
    config: AiOnlyProfileConfig,
    valid_count: int,
    non_nullish: int,
) -> ColumnProfile:
    invalid_count = non_nullish - valid_count
    valid_ratio = safe_ratio(valid_count, non_nullish)
    profile_cls = profile_class_for_config(config)
    return profile_cls(
        valid_count=valid_count,
        invalid_count=invalid_count,
        valid_ratio=valid_ratio,
    )


def compute_ai_only_column_profiles_batch(
    conn: DuckDBPyConnection,
    batch: list[AiOnlyBatchEntry],
    null_tokens: tuple[str, ...],
) -> dict[str, ColumnProfile]:
    """Count values matching confirmed AI-only configs in one table scan."""
    if not batch:
        return {}

    exprs: list[str] = []
    for entry in batch:
        quoted = quote_identifier(entry.column_name)
        nullish = nullish_predicate(quoted, null_tokens)
        valid = _valid_predicate(quoted, entry.config)
        exprs.append(f"COUNT(*) FILTER (WHERE NOT ({nullish}) AND {valid})")

    row = fetch_aggregate_int_row(conn, f"SELECT {', '.join(exprs)} FROM {RAW_INPUT_TABLE_NAME}")

    profiles: dict[str, ColumnProfile] = {}
    for entry, valid_count in zip(batch, row, strict=True):
        profiles[entry.column_name] = _profile(
            entry.config,
            valid_count,
            entry.counts.non_nullish_count,
        )
    return profiles
