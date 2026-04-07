"""Decimal-family profiling stats — decimal, percentage, and signed types."""

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
    decimal_stats_profile_class_for_config,
)

from profiling.column_stats.common import compute_decimal_parse_stats_batch


@dataclass(frozen=True)
class DecimalFamilyBatchEntry:
    column_name: str
    config: DecimalColumnConfig | PercentageColumnConfig | SignedColumnConfig
    counts: ColumnCounts
    value_expr: str


def compute_decimal_family_profiles_batch(
    conn: DuckDBPyConnection,
    batch: list[DecimalFamilyBatchEntry],
    null_tokens: tuple[str, ...],
) -> dict[str, ColumnProfile]:
    """Compute decimal-family profiles for all columns in a single table scan."""
    stats_by_name = compute_decimal_parse_stats_batch(conn, batch, null_tokens)

    profiles: dict[str, ColumnProfile] = {}
    for entry in batch:
        stats = stats_by_name[entry.column_name]
        profile_cls = decimal_stats_profile_class_for_config(entry.config)
        profiles[entry.column_name] = profile_cls(
            parse_match_count=stats.parse_match_count,
            parse_match_ratio=stats.parse_match_ratio,
            swapped_match_count=stats.swapped_match_count,
            swapped_match_ratio=stats.swapped_match_ratio,
            separator_mismatch_detected=stats.separator_mismatch_detected,
        )
    return profiles
