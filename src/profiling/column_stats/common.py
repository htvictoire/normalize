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
from shared.parsing.numeric import (
    decimal_pattern_regex,
    decimal_separator_sql,
    strip_group_only_sql,
)


@dataclass(frozen=True)
class DecimalParseStats:
    """Parse-match and decimal-notation counts for any decimal-syntax column."""

    parse_match_count: int
    parse_match_ratio: float
    comma_decimal_count: int
    dot_decimal_count: int

    @property
    def mixed_number_format_detected(self) -> bool:
        """Both notations appear in the column. Both still parse correctly."""
        return self.comma_decimal_count > 0 and self.dot_decimal_count > 0


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


def _clean_alias(column_name: str) -> str:
    return quote_identifier(f"__clean__{column_name}")


def _nullish_alias(column_name: str) -> str:
    return quote_identifier(f"__nullish__{column_name}")


def _separator_alias(column_name: str) -> str:
    return quote_identifier(f"__sep__{column_name}")


def parse_match_count_exprs(
    column_name: str,
    config: DecimalSyntaxColumnConfig,
) -> tuple[str, str, str]:
    """Return (parse_match, comma_decimal, dot_decimal) COUNT(*) FILTER fragments.

    The notation counts exist to *report* a mixed-locale column, not to reject one:
    the parser resolves each value's separator on its own.

    All three read values pre-computed by ``compute_decimal_parse_stats_batch``, so
    the locale detection runs once per cell rather than once per aggregate.
    """
    cleaned = _clean_alias(column_name)
    separator = _separator_alias(column_name)
    pattern = quote_string(
        decimal_pattern_regex(allow_leading_decimal_point=config.allow_leading_decimal_point)
    )
    parseable = f"NOT {_nullish_alias(column_name)} AND REGEXP_FULL_MATCH({cleaned}, {pattern})"
    return (
        f"COUNT(*) FILTER (WHERE {parseable})",
        f"COUNT(*) FILTER (WHERE {parseable} AND {separator} = ',')",
        f"COUNT(*) FILTER (WHERE {parseable} AND {separator} = '.')",
    )


def compute_decimal_parse_stats_batch(
    conn: DuckDBPyConnection,
    batch: Sequence[DecimalParseBatchEntry],
    null_tokens: tuple[str, ...],
) -> dict[str, DecimalParseStats]:
    """Compute decimal-style parse stats for all batch entries in a single table scan."""
    if not batch:
        return {}

    # Project the cleaned value, the nullish flag and the resolved decimal separator
    # once per column, then aggregate over that. Inlining them into every
    # COUNT(*) FILTER re-runs the whole locale detection for each aggregate.
    inner = ", ".join(
        f"{strip_group_only_sql(entry.value_expr)} AS {_clean_alias(entry.column_name)}, "
        f"{nullish_predicate(quote_identifier(entry.column_name), null_tokens)} "
        f"AS {_nullish_alias(entry.column_name)}"
        for entry in batch
    )
    outer = ", ".join(
        f"{_clean_alias(entry.column_name)}, {_nullish_alias(entry.column_name)}, "
        f"{decimal_separator_sql(_clean_alias(entry.column_name))} "
        f"AS {_separator_alias(entry.column_name)}"
        for entry in batch
    )
    exprs: list[str] = []
    for entry in batch:
        exprs.extend(parse_match_count_exprs(entry.column_name, entry.config))

    row = fetch_aggregate_int_row(
        conn,
        f"SELECT {', '.join(exprs)} FROM ("
        f"SELECT {outer} FROM (SELECT {inner} FROM {RAW_INPUT_TABLE_NAME}))",
    )

    stats_by_name: dict[str, DecimalParseStats] = {}
    count_groups = group_int_values(row, group_size=3, expected_groups=len(batch))
    for entry, (parse_match_count, comma_decimal_count, dot_decimal_count) in zip(
        batch, count_groups, strict=True
    ):
        non_nullish = entry.counts.non_nullish_count
        stats_by_name[entry.column_name] = DecimalParseStats(
            parse_match_count=parse_match_count,
            parse_match_ratio=safe_ratio(parse_match_count, non_nullish),
            comma_decimal_count=comma_decimal_count,
            dot_decimal_count=dot_decimal_count,
        )
    return stats_by_name
