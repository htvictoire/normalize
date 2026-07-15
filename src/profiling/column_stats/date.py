"""Date/time profiling stats."""

from __future__ import annotations

from dataclasses import dataclass

from duckdb import DuckDBPyConnection

from shared.constants import RAW_INPUT_TABLE_NAME
from shared.db.aggregates import fetch_aggregate_int_row, safe_ratio
from shared.db.sql import nullish_predicate, quote_identifier
from shared.models.column import DateColumnConfig, DateTimeColumnConfig, TimeColumnConfig
from shared.models.profiling import (
    ColumnCounts,
    ColumnProfile,
    DateColumnProfile,
    DateTimeColumnProfile,
    TimeColumnProfile,
)
from shared.parsing.temporal import (
    date_order_match_predicate,
    date_parse_expr,
    datetime_order_match_predicate,
    datetime_parse_expr,
    time_parse_expr,
)


@dataclass(frozen=True)
class DateBatchEntry:
    column_name: str
    config: DateColumnConfig
    counts: ColumnCounts


@dataclass(frozen=True)
class DateTimeBatchEntry:
    column_name: str
    config: DateTimeColumnConfig
    counts: ColumnCounts


@dataclass(frozen=True)
class TimeBatchEntry:
    column_name: str
    config: TimeColumnConfig
    counts: ColumnCounts


def _order_evidence_exprs(nullish: str, day_pred: str, month_pred: str) -> list[str]:
    """Aggregates counting values that parse under both orders vs exactly one."""
    return [
        f"COUNT(*) FILTER (WHERE NOT ({nullish}) AND {day_pred} AND {month_pred})",
        f"COUNT(*) FILTER (WHERE NOT ({nullish}) AND ({day_pred}) != ({month_pred}))",
    ]


def compute_date_column_profiles_batch(
    conn: DuckDBPyConnection,
    batch: list[DateBatchEntry],
    null_tokens: tuple[str, ...],
) -> dict[str, ColumnProfile]:
    """Count date-format matches and order evidence for all date columns in one scan."""
    if not batch:
        return {}

    exprs: list[str] = []
    for entry in batch:
        quoted = quote_identifier(entry.column_name)
        nullish = nullish_predicate(quoted, null_tokens)
        date_expr = date_parse_expr(quoted, entry.config.day_first)
        exprs.append(f"COUNT(*) FILTER (WHERE NOT ({nullish}) AND {date_expr} IS NOT NULL)")
        exprs.extend(
            _order_evidence_exprs(
                nullish,
                date_order_match_predicate(quoted, day_first=True),
                date_order_match_predicate(quoted, day_first=False),
            )
        )

    row = fetch_aggregate_int_row(conn, f"SELECT {', '.join(exprs)} FROM {RAW_INPUT_TABLE_NAME}")

    profiles: dict[str, ColumnProfile] = {}
    for index, entry in enumerate(batch):
        format_match_count, ambiguous_count, decisive_count = row[index * 3 : index * 3 + 3]
        non_nullish = entry.counts.non_nullish_count
        profiles[entry.column_name] = DateColumnProfile(
            format_match_count=format_match_count,
            format_match_ratio=safe_ratio(format_match_count, non_nullish),
            order_ambiguous_count=ambiguous_count,
            order_decisive_count=decisive_count,
        )
    return profiles


def compute_datetime_column_profiles_batch(
    conn: DuckDBPyConnection,
    batch: list[DateTimeBatchEntry],
    null_tokens: tuple[str, ...],
) -> dict[str, ColumnProfile]:
    """Count datetime-format matches and order evidence for all datetime columns in one scan."""
    if not batch:
        return {}

    exprs: list[str] = []
    for entry in batch:
        quoted = quote_identifier(entry.column_name)
        nullish = nullish_predicate(quoted, null_tokens)
        datetime_expr = datetime_parse_expr(quoted, entry.config.day_first)
        exprs.append(f"COUNT(*) FILTER (WHERE NOT ({nullish}) AND {datetime_expr} IS NOT NULL)")
        exprs.extend(
            _order_evidence_exprs(
                nullish,
                datetime_order_match_predicate(quoted, day_first=True),
                datetime_order_match_predicate(quoted, day_first=False),
            )
        )

    row = fetch_aggregate_int_row(conn, f"SELECT {', '.join(exprs)} FROM {RAW_INPUT_TABLE_NAME}")

    profiles: dict[str, ColumnProfile] = {}
    for index, entry in enumerate(batch):
        format_match_count, ambiguous_count, decisive_count = row[index * 3 : index * 3 + 3]
        non_nullish = entry.counts.non_nullish_count
        profiles[entry.column_name] = DateTimeColumnProfile(
            format_match_count=format_match_count,
            format_match_ratio=safe_ratio(format_match_count, non_nullish),
            order_ambiguous_count=ambiguous_count,
            order_decisive_count=decisive_count,
        )
    return profiles


def compute_time_column_profiles_batch(
    conn: DuckDBPyConnection,
    batch: list[TimeBatchEntry],
    null_tokens: tuple[str, ...],
) -> dict[str, ColumnProfile]:
    """Count time-format matches for all time columns in a single table scan."""
    if not batch:
        return {}

    exprs: list[str] = []
    for entry in batch:
        quoted = quote_identifier(entry.column_name)
        nullish = nullish_predicate(quoted, null_tokens)
        time_expr = time_parse_expr(quoted)
        exprs.append(f"COUNT(*) FILTER (WHERE NOT ({nullish}) AND {time_expr} IS NOT NULL)")

    row = fetch_aggregate_int_row(conn, f"SELECT {', '.join(exprs)} FROM {RAW_INPUT_TABLE_NAME}")

    profiles: dict[str, ColumnProfile] = {}
    for entry, format_match_count in zip(batch, row, strict=True):
        non_nullish = entry.counts.non_nullish_count
        profiles[entry.column_name] = TimeColumnProfile(
            format_match_count=format_match_count,
            format_match_ratio=safe_ratio(format_match_count, non_nullish),
        )
    return profiles
