"""Profiling stats canonical remap helpers."""

from __future__ import annotations

from collections.abc import Mapping

from shared.models.profiling import ProfilingStats


def profiling_stats_by_canonical(
    *,
    position_to_canonical: Mapping[str, str],
    profiling_stats: ProfilingStats,
) -> dict[str, dict[str, int]]:
    """Remap position-keyed profiling stats to canonical column names."""
    stats_by_canonical: dict[str, dict[str, int]] = {}
    for position_key, canonical_name in position_to_canonical.items():
        column_stats = profiling_stats.columns[position_key]
        stats_by_canonical[canonical_name] = {
            "nullish_count": column_stats.nullish_count,
            "non_null_count": column_stats.non_null_count,
        }
    return stats_by_canonical
