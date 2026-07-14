"""Temporal type detection and day/month order inference for column type inference.

Match counting runs the canonical format chains from ``shared.parsing.temporal``
via Python's ``strptime``. ``day_first`` follows the order that parses more
values; a tie resolves month-first.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from shared.parsing.temporal import (
    TIME_STRPTIME_FORMATS,
    date_strptime_formats,
    datetime_strptime_formats,
)

_MIN_FOUR_DIGIT_YEAR = 1000


def _matches_any(value: str, formats: Sequence[str]) -> bool:
    for fmt in formats:
        try:
            parsed = datetime.strptime(value, fmt)
        except ValueError:
            continue
        # strptime's %Y accepts 1-3 digit years; sub-1000 years never parse.
        if parsed.year >= _MIN_FOUR_DIGIT_YEAR:
            return True
    return False


def _count_matches(values: Sequence[str], formats: Sequence[str]) -> int:
    return sum(1 for value in values if _matches_any(value, formats))


def _best_day_first(
    values: Sequence[str],
    chain_for: Sequence[str],
    chain_against: Sequence[str],
) -> tuple[bool, int]:
    """Return (day_first, match_count) for the order that parses more values."""
    day_count = _count_matches(values, chain_for)
    month_count = _count_matches(values, chain_against)
    if day_count > month_count:
        return True, day_count
    return False, month_count


def infer_date_day_first(values: Sequence[str]) -> tuple[bool, int]:
    """Return (day_first, match_count) for values read as dates."""
    return _best_day_first(
        values,
        date_strptime_formats(day_first=True),
        date_strptime_formats(day_first=False),
    )


def infer_datetime_day_first(values: Sequence[str]) -> tuple[bool, int]:
    """Return (day_first, match_count) for values read as datetimes."""
    return _best_day_first(
        values,
        datetime_strptime_formats(day_first=True),
        datetime_strptime_formats(day_first=False),
    )


def count_time_matches(values: Sequence[str]) -> int:
    """Return how many values parse as a time of day."""
    return _count_matches(values, TIME_STRPTIME_FORMATS)
