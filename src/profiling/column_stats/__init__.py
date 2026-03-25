"""Compute per-type column profiles from a live DuckDB table."""

from profiling.column_stats.dispatch import compute_column_profile

__all__ = ["compute_column_profile"]
