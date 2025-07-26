"""Shared profiling models produced by suggestion and consumed by app/normalize."""

from shared.models.base import MainModel


class ProfilingColumnStats(MainModel):
    """Per-column lightweight profiling stats produced by suggestion."""

    nullish_count: int
    non_null_count: int


class ProfilingStats(MainModel):
    """Suggestion-phase profiling output."""

    row_count: int
    columns: dict[str, ProfilingColumnStats]
