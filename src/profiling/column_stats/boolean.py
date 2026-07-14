"""Boolean profiling stats."""

from __future__ import annotations

from dataclasses import dataclass

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.aggregates import fetch_aggregate_int_row, group_int_values, safe_ratio
from shared.db.sql import nullish_predicate, quote_identifier, quote_string
from shared.models.profiling import BooleanColumnProfile, ColumnCounts, ColumnProfile
from shared.parsing.boolean import BOOLEAN_FALSE_TOKENS, BOOLEAN_TRUE_TOKENS

_TRUE_IN = ", ".join(quote_string(t) for t in sorted(BOOLEAN_TRUE_TOKENS))
_FALSE_IN = ", ".join(quote_string(t) for t in sorted(BOOLEAN_FALSE_TOKENS))


@dataclass(frozen=True)
class BooleanBatchEntry:
    column_name: str
    counts: ColumnCounts


def make_boolean_batch_entry(column_name: str, counts: ColumnCounts) -> BooleanBatchEntry:
    """Build a BooleanBatchEntry for one boolean column."""
    return BooleanBatchEntry(column_name=column_name, counts=counts)


def compute_boolean_column_profiles_batch(
    conn: DuckDBPyConnection,
    batch: list[BooleanBatchEntry],
    null_tokens: tuple[str, ...],
) -> dict[str, ColumnProfile]:
    """Count true/false/unrecognized values for all boolean columns in a single table scan."""
    if not batch:
        return {}

    exprs: list[str] = []
    for entry in batch:
        quoted = quote_identifier(entry.column_name)
        nullish = nullish_predicate(quoted, null_tokens)
        normalized = f"LOWER(TRIM(CAST({quoted} AS VARCHAR)))"
        exprs.append(
            f"COUNT(*) FILTER (WHERE NOT ({nullish}) AND {normalized} IN ({_TRUE_IN}))"
        )
        exprs.append(
            f"COUNT(*) FILTER (WHERE NOT ({nullish}) AND {normalized} IN ({_FALSE_IN}))"
        )

    row = fetch_aggregate_int_row(conn, f"SELECT {', '.join(exprs)} FROM {RAW_INPUT_TABLE_NAME}")

    profiles: dict[str, ColumnProfile] = {}
    count_pairs = group_int_values(row, group_size=2, expected_groups=len(batch))
    for entry, (true_count, false_count) in zip(batch, count_pairs, strict=True):
        non_nullish = entry.counts.non_nullish_count
        profiles[entry.column_name] = BooleanColumnProfile(
            true_token_count=true_count,
            false_token_count=false_count,
            unrecognized_count=non_nullish - true_count - false_count,
            recognized_ratio=safe_ratio(true_count + false_count, non_nullish),
        )
    return profiles
