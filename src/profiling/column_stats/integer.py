"""Integer profiling stats."""

from __future__ import annotations

from dataclasses import dataclass

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.aggregates import fetch_aggregate_int_row, safe_ratio
from shared.db.sql import nullish_predicate, quote_identifier, quote_string
from shared.models.column import IntegerColumnConfig
from shared.models.profiling import ColumnCounts, ColumnProfile, IntegerColumnProfile
from shared.parsing.numeric import integer_pattern_regex, strip_group_only_sql


@dataclass(frozen=True)
class IntegerBatchEntry:
    column_name: str
    config: IntegerColumnConfig
    counts: ColumnCounts
    value_expr: str


def compute_integer_column_profiles_batch(
    conn: DuckDBPyConnection,
    batch: list[IntegerBatchEntry],
    null_tokens: tuple[str, ...],
) -> dict[str, ColumnProfile]:
    """Count integer-pattern matches for all columns in a single table scan."""
    if not batch:
        return {}

    exprs: list[str] = []
    for entry in batch:
        quoted = quote_identifier(entry.column_name)
        nullish = nullish_predicate(quoted, null_tokens)
        pattern = integer_pattern_regex()
        exprs.append(
            f"COUNT(*) FILTER (WHERE NOT ({nullish})"
            f" AND REGEXP_FULL_MATCH({strip_group_only_sql(entry.value_expr)},"
            f" {quote_string(pattern)}))"
        )

    row = fetch_aggregate_int_row(conn, f"SELECT {', '.join(exprs)} FROM {RAW_INPUT_TABLE_NAME}")

    profiles: dict[str, ColumnProfile] = {}
    for entry, parse_match_count in zip(batch, row, strict=True):
        non_nullish = entry.counts.non_nullish_count
        profiles[entry.column_name] = IntegerColumnProfile(
            parse_match_count=parse_match_count,
            parse_match_ratio=safe_ratio(parse_match_count, non_nullish),
        )
    return profiles
