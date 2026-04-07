"""String profiling stats."""

from __future__ import annotations

from dataclasses import dataclass

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.sql import nullish_predicate, quote_identifier
from shared.models.profiling import ColumnCounts, ColumnProfile, StringColumnProfile

from profiling.aggregates import fetch_aggregate_int_row, group_int_values, safe_ratio


@dataclass(frozen=True)
class StringBatchEntry:
    column_name: str
    counts: ColumnCounts


def compute_string_column_profiles_batch(
    conn: DuckDBPyConnection,
    batch: list[StringBatchEntry],
    null_tokens: tuple[str, ...],
) -> dict[str, ColumnProfile]:
    """Compute distinct/length stats for all string columns in a single table scan."""
    if not batch:
        return {}

    exprs: list[str] = []
    for entry in batch:
        quoted = quote_identifier(entry.column_name)
        nullish = nullish_predicate(quoted, null_tokens)
        val_expr = f"TRIM(CAST({quoted} AS VARCHAR))"
        exprs.append(f"COUNT(DISTINCT {val_expr}) FILTER (WHERE NOT ({nullish}))")
        exprs.append(f"COALESCE(MIN(LENGTH({val_expr})) FILTER (WHERE NOT ({nullish})), 0)")
        exprs.append(f"COALESCE(MAX(LENGTH({val_expr})) FILTER (WHERE NOT ({nullish})), 0)")

    row = fetch_aggregate_int_row(conn, f"SELECT {', '.join(exprs)} FROM {RAW_INPUT_TABLE_NAME}")

    profiles: dict[str, ColumnProfile] = {}
    count_triples = group_int_values(row, group_size=3, expected_groups=len(batch))
    for entry, (distinct_count, min_length, max_length) in zip(
        batch, count_triples, strict=True
    ):
        non_nullish = entry.counts.non_nullish_count
        profiles[entry.column_name] = StringColumnProfile(
            distinct_count=distinct_count,
            distinct_ratio=safe_ratio(distinct_count, non_nullish),
            min_length=min_length,
            max_length=max_length,
        )
    return profiles
