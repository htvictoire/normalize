"""Shared helpers for profiling column-stat SQL fragments."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.aggregates import fetch_aggregate_int_row, group_int_values, safe_ratio
from shared.db.sql import nullish_predicate, quote_identifier, quote_string
from shared.models.column.base import DecimalSyntaxColumnConfig
from shared.models.profiling import ColumnCounts
from shared.parsing.numeric import decimal_pattern_regex


@dataclass(frozen=True)
class DecimalParseStats:
    """Parse-match and swapped-separator counts for any decimal-syntax column."""

    parse_match_count: int
    parse_match_ratio: float
    swapped_match_count: int
    swapped_match_ratio: float

    @property
    def separator_mismatch_detected(self) -> bool:
        return self.swapped_match_count > self.parse_match_count


class DecimalParseBatchEntry(Protocol):
    """Shared shape for batched decimal-syntax parse profiling inputs."""

    @property
    def column_name(self) -> str: ...

    @property
    def config(self) -> DecimalSyntaxColumnConfig: ...

    @property
    def counts(self) -> ColumnCounts: ...

    @property
    def value_expr(self) -> str: ...


def parse_match_count_exprs(
    column_name: str,
    config: DecimalSyntaxColumnConfig,
    value_expr: str,
    null_tokens: tuple[str, ...],
) -> tuple[str, str]:
    """Return (declared_expr, swapped_expr) COUNT(*) FILTER SQL fragments for one column."""
    quoted = quote_identifier(column_name)
    nullish = nullish_predicate(quoted, null_tokens)
    declared = decimal_pattern_regex(
        decimal_separator=config.decimal_separator,
        thousand_separator=config.thousand_separator,
        grouping_style=config.grouping_style,
        allow_leading_decimal_point=config.allow_leading_decimal_point,
    )
    swapped = decimal_pattern_regex(
        decimal_separator=config.thousand_separator,
        thousand_separator=config.decimal_separator,
        grouping_style=config.grouping_style,
        allow_leading_decimal_point=config.allow_leading_decimal_point,
    )
    dp = quote_string(declared)
    sp = quote_string(swapped)
    return (
        f"COUNT(*) FILTER (WHERE NOT ({nullish}) AND REGEXP_FULL_MATCH({value_expr}, {dp}))",
        f"COUNT(*) FILTER (WHERE NOT ({nullish}) AND REGEXP_FULL_MATCH({value_expr}, {sp}))",
    )


def compute_decimal_parse_stats_batch(
    conn: DuckDBPyConnection,
    batch: Sequence[DecimalParseBatchEntry],
    null_tokens: tuple[str, ...],
) -> dict[str, DecimalParseStats]:
    """Compute decimal-style parse stats for all batch entries in a single table scan."""
    if not batch:
        return {}

    exprs: list[str] = []
    for entry in batch:
        declared_expr, swapped_expr = parse_match_count_exprs(
            entry.column_name, entry.config, entry.value_expr, null_tokens
        )
        exprs.append(declared_expr)
        exprs.append(swapped_expr)

    row = fetch_aggregate_int_row(conn, f"SELECT {', '.join(exprs)} FROM {RAW_INPUT_TABLE_NAME}")

    stats_by_name: dict[str, DecimalParseStats] = {}
    count_pairs = group_int_values(row, group_size=2, expected_groups=len(batch))
    for entry, (parse_match_count, swapped_match_count) in zip(
        batch, count_pairs, strict=True
    ):
        non_nullish = entry.counts.non_nullish_count
        stats_by_name[entry.column_name] = DecimalParseStats(
            parse_match_count=parse_match_count,
            parse_match_ratio=safe_ratio(parse_match_count, non_nullish),
            swapped_match_count=swapped_match_count,
            swapped_match_ratio=safe_ratio(swapped_match_count, non_nullish),
        )
    return stats_by_name
