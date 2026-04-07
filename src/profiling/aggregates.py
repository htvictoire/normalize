"""Shared helpers for aggregate query results and ratio calculations."""

from __future__ import annotations

from collections.abc import Sequence
from typing import SupportsInt, cast

from duckdb import DuckDBPyConnection


def safe_ratio(
    numerator: int | float,
    denominator: int | float,
    *,
    default: float = 1.0,
) -> float:
    """Return ``numerator / denominator`` with an explicit empty-denominator policy."""
    return default if denominator <= 0 else (numerator / denominator)


def fetch_aggregate_int_row(conn: DuckDBPyConnection, query: str) -> tuple[int, ...]:
    """Return the single integer-valued row emitted by an aggregate SELECT."""
    raw_row = cast("tuple[SupportsInt, ...]", conn.execute(query).fetchone())
    return tuple(int(value) for value in raw_row)


def group_int_values(
    values: Sequence[int],
    *,
    group_size: int,
    expected_groups: int | None = None,
) -> tuple[tuple[int, ...], ...]:
    """Split aggregate values into fixed-width groups and validate the row shape."""
    if group_size <= 0:
        raise ValueError("group_size must be positive")

    total_values = len(values)
    if expected_groups is None:
        if total_values % group_size != 0:
            raise ValueError(
                f"Expected aggregate row length divisible by {group_size}, got {total_values}"
            )
    else:
        expected_length = group_size * expected_groups
        if total_values != expected_length:
            raise ValueError(
                f"Expected aggregate row length {expected_length}, got {total_values}"
            )

    return tuple(
        tuple(values[start : start + group_size])
        for start in range(0, total_values, group_size)
    )
