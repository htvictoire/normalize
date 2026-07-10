"""Date/time profiling stats."""

from __future__ import annotations

from dataclasses import dataclass

from duckdb import DuckDBPyConnection

from shared.constants import EXCEL_SERIAL_DATE_EPOCH_SQL, RAW_INPUT_TABLE_NAME
from shared.db.aggregates import fetch_aggregate_int_row, safe_ratio
from shared.db.sql import nullish_predicate, quote_identifier, quote_string
from shared.models.column import DateColumnConfig, DateTimeColumnConfig, TimeColumnConfig
from shared.models.profiling import (
    ColumnCounts,
    ColumnProfile,
    DateColumnProfile,
    DateTimeColumnProfile,
    TimeColumnProfile,
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


def compute_date_column_profiles_batch(
    conn: DuckDBPyConnection,
    batch: list[DateBatchEntry],
    null_tokens: tuple[str, ...],
) -> dict[str, ColumnProfile]:
    """Count date-format matches for all date columns in a single table scan."""
    if not batch:
        return {}

    exprs: list[str] = []
    for entry in batch:
        quoted = quote_identifier(entry.column_name)
        nullish = nullish_predicate(quoted, null_tokens)
        if entry.config.date_format == "EXCEL_SERIAL":
            date_expr = f"({EXCEL_SERIAL_DATE_EPOCH_SQL} + TRY_CAST({quoted} AS INTEGER))"
        else:
            fmt = quote_string(entry.config.date_format)
            date_expr = f"TRY_CAST(TRY_STRPTIME({quoted}, {fmt}) AS DATE)"
        exprs.append(
            f"COUNT(*) FILTER (WHERE NOT ({nullish}) AND {date_expr} IS NOT NULL)"
        )

    row = fetch_aggregate_int_row(conn, f"SELECT {', '.join(exprs)} FROM {RAW_INPUT_TABLE_NAME}")

    profiles: dict[str, ColumnProfile] = {}
    for entry, format_match_count in zip(batch, row, strict=True):
        non_nullish = entry.counts.non_nullish_count
        profiles[entry.column_name] = DateColumnProfile(
            format_match_count=format_match_count,
            format_match_ratio=safe_ratio(format_match_count, non_nullish),
        )
    return profiles


def compute_datetime_column_profiles_batch(
    conn: DuckDBPyConnection,
    batch: list[DateTimeBatchEntry],
    null_tokens: tuple[str, ...],
) -> dict[str, ColumnProfile]:
    """Count datetime-format matches for all datetime columns in a single table scan."""
    if not batch:
        return {}

    exprs: list[str] = []
    for entry in batch:
        quoted = quote_identifier(entry.column_name)
        nullish = nullish_predicate(quoted, null_tokens)
        if entry.config.datetime_format == "EXCEL_SERIAL":
            datetime_expr = (
                f"({EXCEL_SERIAL_DATE_EPOCH_SQL} + "
                f"(TRY_CAST({quoted} AS DOUBLE) * INTERVAL 1 DAY))"
            )
        else:
            fmt = quote_string(entry.config.datetime_format)
            datetime_expr = f"TRY_CAST(TRY_STRPTIME({quoted}, {fmt}) AS TIMESTAMP)"
        exprs.append(
            f"COUNT(*) FILTER (WHERE NOT ({nullish}) AND {datetime_expr} IS NOT NULL)"
        )

    row = fetch_aggregate_int_row(conn, f"SELECT {', '.join(exprs)} FROM {RAW_INPUT_TABLE_NAME}")

    profiles: dict[str, ColumnProfile] = {}
    for entry, format_match_count in zip(batch, row, strict=True):
        non_nullish = entry.counts.non_nullish_count
        profiles[entry.column_name] = DateTimeColumnProfile(
            format_match_count=format_match_count,
            format_match_ratio=safe_ratio(format_match_count, non_nullish),
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
        fmt = quote_string(entry.config.time_format)
        time_expr = f"TRY_CAST(TRY_STRPTIME({quoted}, {fmt}) AS TIME)"
        exprs.append(
            f"COUNT(*) FILTER (WHERE NOT ({nullish}) AND {time_expr} IS NOT NULL)"
        )

    row = fetch_aggregate_int_row(conn, f"SELECT {', '.join(exprs)} FROM {RAW_INPUT_TABLE_NAME}")

    profiles: dict[str, ColumnProfile] = {}
    for entry, format_match_count in zip(batch, row, strict=True):
        non_nullish = entry.counts.non_nullish_count
        profiles[entry.column_name] = TimeColumnProfile(
            format_match_count=format_match_count,
            format_match_ratio=safe_ratio(format_match_count, non_nullish),
        )
    return profiles
