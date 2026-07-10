"""Identifier profiling stats."""

from __future__ import annotations

from dataclasses import dataclass

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.aggregates import fetch_aggregate_int_row, group_int_values, safe_ratio
from shared.db.sql import nullish_predicate, quote_identifier
from shared.models.profiling import ColumnCounts, ColumnProfile, IdentifierColumnProfile


@dataclass(frozen=True)
class IdentifierBatchEntry:
    column_name: str
    counts: ColumnCounts


def compute_identifier_column_profiles_batch(
    conn: DuckDBPyConnection,
    batch: list[IdentifierBatchEntry],
    null_tokens: tuple[str, ...],
) -> dict[str, ColumnProfile]:
    """Compute uniqueness/length stats for identifier columns in a single scan."""
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
        duplicate_count = non_nullish - distinct_count
        uniqueness_ratio = safe_ratio(distinct_count, non_nullish)
        profiles[entry.column_name] = IdentifierColumnProfile(
            distinct_count=distinct_count,
            distinct_ratio=uniqueness_ratio,
            duplicate_count=duplicate_count,
            uniqueness_ratio=uniqueness_ratio,
            min_length=min_length,
            max_length=max_length,
        )
    return profiles
