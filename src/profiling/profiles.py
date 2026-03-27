"""Pipeline-level column profile assembly for profiling."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from duckdb import DuckDBPyConnection

from shared.models.column import ColumnConfig, column_config_type
from shared.models.issues import NormalizationIssue
from shared.models.profiling import ColumnCounts, ColumnProfileStats

from profiling.column_stats import compute_column_profile
from profiling.constants import NUMERIC_MISMATCH_THRESHOLD
from profiling.issues import collect_column_issues


@dataclass(frozen=True)
class ProfileResults:
    """Per-column profiling output plus aggregate quality ratios."""

    column_stats: dict[str, ColumnProfileStats]
    issues: list[NormalizationIssue]
    completeness_ratio: float
    pattern_consistency_ratio: float


def compute_profile_results(
    conn: DuckDBPyConnection,
    *,
    position_to_name: Mapping[str, str],
    column_config: Mapping[str, ColumnConfig],
    null_tokens: tuple[str, ...],
    counts_by_position: Mapping[str, ColumnCounts],
    row_count: int,
) -> ProfileResults:
    """Return per-column profile stats, issues, and aggregate profiling ratios."""
    issues: list[NormalizationIssue] = []
    column_stats: dict[str, ColumnProfileStats] = {}
    currency_ratios: list[float] = []
    total_non_nullish_cells = 0

    for position, column_name in position_to_name.items():
        config = column_config[position]
        counts = counts_by_position[position]
        total_non_nullish_cells += counts.non_nullish_count
        null_ratio = 0.0 if row_count <= 0 else (counts.null_count / row_count)
        nullish_ratio = 0.0 if row_count <= 0 else (counts.nullish_count / row_count)

        type_profile = compute_column_profile(
            conn,
            column_name=column_name,
            config=config,
            null_tokens=null_tokens,
            counts=counts,
        )
        collect_column_issues(
            column_name,
            config,
            type_profile,
            issues,
            currency_ratios,
            numeric_threshold=NUMERIC_MISMATCH_THRESHOLD,
        )

        column_stats[position] = ColumnProfileStats(
            label=column_name,
            column_type=column_config_type(config),
            counts=counts,
            null_ratio=null_ratio,
            nullish_ratio=nullish_ratio,
            type_profile=type_profile,
        )

    column_count = len(position_to_name)
    total_cells = row_count * column_count
    completeness_ratio = 1.0 if total_cells <= 0 else (total_non_nullish_cells / total_cells)
    pattern_consistency_ratio = (
        1.0 if not currency_ratios else (sum(currency_ratios) / len(currency_ratios))
    )
    return ProfileResults(
        column_stats=column_stats,
        issues=issues,
        completeness_ratio=completeness_ratio,
        pattern_consistency_ratio=pattern_consistency_ratio,
    )
