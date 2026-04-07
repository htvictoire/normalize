"""Pipeline-level column profile assembly for profiling."""

from __future__ import annotations

from dataclasses import dataclass

from duckdb import DuckDBPyConnection

from shared.models.column import ColumnConfig, column_config_type
from shared.models.issues import NormalizationIssue
from shared.models.profiling import ColumnCounts, ColumnProfileStats, SymbolDistributionProfile

from profiling.aggregates import safe_ratio
from profiling.column_stats import compute_column_profiles
from profiling.constants import NUMERIC_MISMATCH_THRESHOLD
from profiling.issues import collect_column_issues


@dataclass(frozen=True)
class ProfileResults:
    """Per-column profiling output plus aggregate quality ratios."""

    column_stats: dict[str, ColumnProfileStats]
    issues: list[NormalizationIssue]
    completeness_ratio: float
    mean_dominant_symbol_ratio: float


def compute_profile_results(
    conn: DuckDBPyConnection,
    columns: list[str],
    column_config: dict[str, ColumnConfig],
    null_tokens: tuple[str, ...],
    counts_by_name: dict[str, ColumnCounts],
    row_count: int,
) -> ProfileResults:
    """Return per-column profile stats, issues, and aggregate profiling ratios."""
    type_profiles = compute_column_profiles(
        conn,
        columns=columns,
        column_config=column_config,
        null_tokens=null_tokens,
        counts_by_name=counts_by_name,
    )

    issues: list[NormalizationIssue] = []
    column_stats: dict[str, ColumnProfileStats] = {}
    dominant_symbol_ratio_sum = 0.0
    dominant_symbol_ratio_count = 0
    total_non_nullish_cells = 0

    for col_name in columns:
        config = column_config[col_name]
        counts = counts_by_name[col_name]
        type_profile = type_profiles[col_name]

        total_non_nullish_cells += counts.non_nullish_count
        null_ratio = safe_ratio(counts.null_count, row_count, default=0.0)
        nullish_ratio = safe_ratio(counts.nullish_count, row_count, default=0.0)

        issues.extend(collect_column_issues(
            column_name=col_name,
            config=config,
            profile=type_profile,
            numeric_threshold=NUMERIC_MISMATCH_THRESHOLD,
        ))

        if isinstance(type_profile, SymbolDistributionProfile):
            dominant_symbol_ratio_sum += type_profile.dominant_symbol_ratio
            dominant_symbol_ratio_count += 1

        column_stats[col_name] = ColumnProfileStats(
            label=col_name,
            column_type=column_config_type(config),
            counts=counts,
            null_ratio=null_ratio,
            nullish_ratio=nullish_ratio,
            type_profile=type_profile,
        )

    column_count = len(columns)
    total_cells = row_count * column_count
    completeness_ratio = safe_ratio(total_non_nullish_cells, total_cells)
    mean_dominant_symbol_ratio = safe_ratio(
        dominant_symbol_ratio_sum,
        dominant_symbol_ratio_count,
    )
    return ProfileResults(
        column_stats=column_stats,
        issues=issues,
        completeness_ratio=completeness_ratio,
        mean_dominant_symbol_ratio=mean_dominant_symbol_ratio,
    )
