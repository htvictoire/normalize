"""Scalar value normalization utilities."""

from __future__ import annotations


def normalize_cell_value(value: object) -> str | None:
    """Cast a raw cell to a stripped string, returning None if null or blank."""
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized if normalized else None
