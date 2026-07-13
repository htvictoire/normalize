"""Decimal-stats profiling for decimal, percentage, and signed types."""

from __future__ import annotations

from dataclasses import dataclass

from duckdb import DuckDBPyConnection

from shared.models.column import (
    DecimalColumnConfig,
    PercentageColumnConfig,
    SignedColumnConfig,
)
from shared.models.profiling import (
    ColumnCounts,
    ColumnProfile,
    profile_class_for_config,
)

from profiling.column_stats.common import compute_decimal_parse_stats_batch


@dataclass(frozen=True)
class DecimalStatsBatchEntry:
    column_name: str
    config: DecimalColumnConfig | PercentageColumnConfig | SignedColumnConfig
    counts: ColumnCounts
    value_expr: str


def compute_decimal_stats_profiles_batch(
    conn: DuckDBPyConnection,
    batch: list[DecimalStatsBatchEntry],
    null_tokens: tuple[str, ...],
) -> dict[str, ColumnProfile]:
    """Compute decimal/percentage/signed profiles in a single table scan."""
    stats_by_name = compute_decimal_parse_stats_batch(conn, batch, null_tokens)

    profiles: dict[str, ColumnProfile] = {}
    for entry in batch:
        stats = stats_by_name[entry.column_name]
        profile_cls = profile_class_for_config(entry.config)
        profiles[entry.column_name] = profile_cls(
            parse_match_count=stats.parse_match_count,
            parse_match_ratio=stats.parse_match_ratio,
            comma_decimal_count=stats.comma_decimal_count,
            dot_decimal_count=stats.dot_decimal_count,
            mixed_number_format_detected=stats.mixed_number_format_detected,
        )
    return profiles
