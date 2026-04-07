"""Shared helpers for aggregate query decoding and ratio calculations."""

from __future__ import annotations

from collections.abc import Sequence

from duckdb import DuckDBPyConnection


def safe_ratio(
    numerator: int | float,
    denominator: int | float,
    *,
    default: float = 1.0,
) -> float:
    """Return ``numerator / denominator`` with an explicit empty-denominator policy."""
    return default if denominator <= 0 else (numerator / denominator)


def fetch_aggregate_int_row(
    conn: DuckDBPyConnection,
    query: str,
    params: Sequence[object] = (),
) -> tuple[int, ...]:
    """Return the single integer-valued row emitted by an aggregate SELECT."""
    raw_row = conn.execute(query, params).fetchone()
    if raw_row is None:
        raise ValueError("Aggregate query returned no row")

    typed_values: list[int] = []
    for value in raw_row:
        try:
            typed_values.append(int(value))
        except (TypeError, ValueError) as exc:
            raise TypeError("Aggregate query row contained a non-integer value") from exc
    return tuple(typed_values)


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
