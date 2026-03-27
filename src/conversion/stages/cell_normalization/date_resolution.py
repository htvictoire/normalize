"""Helpers for resolving position-keyed date formats to canonical columns."""

from __future__ import annotations

from collections.abc import Mapping


def resolve_date_formats_by_canonical(
    date_formats: Mapping[str, str] | None,
    position_to_canonical: Mapping[str, str],
) -> dict[str, str]:
    """Resolve declared position-key date formats to canonical column names."""
    resolved: dict[str, str] = {}
    if date_formats is None:
        return resolved
    for position_key, format_string in date_formats.items():
        canonical_name = position_to_canonical.get(position_key)
        if canonical_name is None:
            continue
        resolved[canonical_name] = format_string
    return resolved
