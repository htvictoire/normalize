"""Boolean profiling stats."""

from __future__ import annotations

from dataclasses import dataclass

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.aggregates import fetch_aggregate_int_row, group_int_values, safe_ratio
from shared.db.sql import normalize_tokens, nullish_predicate, quote_identifier, quote_string
from shared.models.column import BooleanColumnConfig
from shared.models.profiling import BooleanColumnProfile, ColumnCounts, ColumnProfile


@dataclass(frozen=True)
class BooleanBatchEntry:
    column_name: str
    counts: ColumnCounts
    true_in_sql: str
    false_in_sql: str


def make_boolean_batch_entry(
    column_name: str, config: BooleanColumnConfig, counts: ColumnCounts
) -> BooleanBatchEntry:
    """Build a BooleanBatchEntry, normalizing and formatting token sets once."""
    return BooleanBatchEntry(
        column_name=column_name,
        counts=counts,
        true_in_sql=_in_clause(config.true_tokens),
        false_in_sql=_in_clause(config.false_tokens),
    )


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
            f"COUNT(*) FILTER (WHERE NOT ({nullish}) AND {normalized} IN ({entry.true_in_sql}))"
        )
        exprs.append(
            f"COUNT(*) FILTER (WHERE NOT ({nullish}) AND {normalized} IN ({entry.false_in_sql}))"
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


def _in_clause(tokens: tuple[str, ...]) -> str:
    normalized = normalize_tokens(tokens)
    if not normalized:
        return "''"
    return ", ".join(quote_string(token) for token in normalized)
