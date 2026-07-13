"""Shared helpers for source format inference."""

from __future__ import annotations

import re

# A cell containing only a number: optional sign, then digit runs separated by
# grouping or decimal marks. Anchored, so `fy2023` and `2023-01-03` are not numbers.
_NUMERIC_LITERAL = re.compile(r"[+-]?\d+(?:[.,\s']\d+)*")


def is_numeric_literal(value: str) -> bool:
    """Return True when value is a bare number."""
    return _NUMERIC_LITERAL.fullmatch(value.strip()) is not None


def is_header_like(values: list[str]) -> bool:
    """Return True when a row names columns rather than carrying data.

    A header labels every cell it spans and contains no bare numbers. The first
    condition rejects title and marker rows, which label one or two cells and leave
    the rest blank; the second rejects data rows, which are fully populated.

    Labelling is required of every cell rather than a majority so the test does not
    vary with column count. The cost is that a header containing a blank cell is not
    recognised here; csv.Sniffer covers that case ahead of the scan.
    """
    cells = [value.strip() for value in values]
    if not cells or not all(cells):
        return False
    return not any(is_numeric_literal(cell) for cell in cells)
