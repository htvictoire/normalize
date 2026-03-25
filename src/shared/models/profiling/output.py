"""Profiling output models: per-column stats and full pipeline output."""

from __future__ import annotations

from shared.models.base import MainModel
from shared.models.column import ColumnType
from shared.models.issues import NormalizationIssue
from shared.models.profiling.base import ColumnCounts
from shared.models.profiling.profiles import ColumnProfile


class ColumnProfileStats(MainModel):
    label: str
    column_type: ColumnType
    counts: ColumnCounts
    null_ratio: float
    nullish_ratio: float
    type_profile: ColumnProfile


class ProfilingOutput(MainModel):
    source_checksum: str
    row_count: int
    empty_row_count: int
    column_count: int
    pattern_consistency_ratio: float
    completeness_ratio: float
    column_stats: dict[str, ColumnProfileStats]
    issues: list[NormalizationIssue]
