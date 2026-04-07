"""Compute per-type column profiles from a live DuckDB table."""

from profiling.column_stats.dispatch import compute_column_profiles

__all__ = ["compute_column_profiles"]
