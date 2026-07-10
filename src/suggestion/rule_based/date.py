"""Date format detection for column type inference."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from suggestion.rule_based.constants import (
    DATE_FORMAT_CANDIDATES,
    DATE_FORMAT_RANK,
    DATETIME_FORMAT_CANDIDATES,
    DATETIME_FORMAT_RANK,
    TIME_FORMAT_CANDIDATES,
    TIME_FORMAT_RANK,
)


def _match_format(value: str, candidates: Sequence[str]) -> str | None:
    """Return the first candidate format that parses ``value``, or None."""
    for date_format in candidates:
        try:
            datetime.strptime(value, date_format)
        except ValueError:
            continue
        return date_format
    return None


def _best_format(
    values: Sequence[str],
    candidates: Sequence[str],
    rank: dict[str, int],
) -> tuple[str | None, int]:
    """Return (best_format, match_count) for the format with the most matches."""
    counts: dict[str, int] = dict.fromkeys(candidates, 0)
    for value in values:
        fmt = _match_format(value, candidates)
        if fmt is not None:
            counts[fmt] += 1
    best_fmt, best_count = max(
        counts.items(), key=lambda item: (item[1], -rank[item[0]])
    )
    return (best_fmt, best_count) if best_count > 0 else (None, 0)


def match_date_format(value: str) -> str | None:
    """Return the first DATE_FORMAT_CANDIDATES format that parses ``value``, or None."""
    return _match_format(value, DATE_FORMAT_CANDIDATES)


def match_datetime_format(value: str) -> str | None:
    """Return the first DATETIME_FORMAT_CANDIDATES format that parses ``value``, or None."""
    return _match_format(value, DATETIME_FORMAT_CANDIDATES)


def match_time_format(value: str) -> str | None:
    """Return the first TIME_FORMAT_CANDIDATES format that parses ``value``, or None."""
    return _match_format(value, TIME_FORMAT_CANDIDATES)


def best_date_format(values: Sequence[str]) -> tuple[str | None, int]:
    """Return (best_format, match_count) for the date format with the most matches."""
    return _best_format(values, DATE_FORMAT_CANDIDATES, DATE_FORMAT_RANK)


def best_datetime_format(values: Sequence[str]) -> tuple[str | None, int]:
    """Return (best_format, match_count) for the datetime format with the most matches."""
    return _best_format(values, DATETIME_FORMAT_CANDIDATES, DATETIME_FORMAT_RANK)


def best_time_format(values: Sequence[str]) -> tuple[str | None, int]:
    """Return (best_format, match_count) for the time format with the most matches."""
    return _best_format(values, TIME_FORMAT_CANDIDATES, TIME_FORMAT_RANK)
