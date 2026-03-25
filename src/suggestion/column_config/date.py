"""Date format detection for column type inference."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from suggestion.constants import DATE_FORMAT_CANDIDATES


def match_date_format(value: str) -> str | None:
    """Return the first DATE_FORMAT_CANDIDATES format that parses ``value``, or None."""
    for date_format in DATE_FORMAT_CANDIDATES:
        try:
            datetime.strptime(value, date_format)
        except ValueError:
            continue
        return date_format
    return None


def best_date_format(values: Sequence[str]) -> tuple[str | None, int]:
    """Return (best_format, match_count) for the date format with the most matches."""
    counts: dict[str, int] = dict.fromkeys(DATE_FORMAT_CANDIDATES, 0)
    for value in values:
        fmt = match_date_format(value)
        if fmt is not None:
            counts[fmt] += 1
    best_fmt, best_count = max(counts.items(), key=lambda item: item[1])
    return (best_fmt, best_count) if best_count > 0 else (None, 0)
