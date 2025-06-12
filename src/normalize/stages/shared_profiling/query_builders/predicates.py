"""Predicate fragments for shared profile query builders."""

from __future__ import annotations

from collections.abc import Sequence

from normalize.stages.shared_profiling.sql_helpers import quote_string


def has_any_separator_predicate(base_value: str, separators: Sequence[str]) -> str:
    """Return predicate checking whether value contains any configured separators."""
    unique_separators = sorted({separator for separator in separators if separator})
    if not unique_separators:
        return "FALSE"
    return " OR ".join(
        f"STRPOS({base_value}, {quote_string(separator)}) > 0"
        for separator in unique_separators
    )


def swapped_float_predicate(
    swapped_float_template: str,
    base_value: str,
    normalized_swapped_alias: str,
) -> str:
    """Fill swapped-locale predicate template with per-column aliases."""
    return (
        swapped_float_template.replace("BASE_VALUE_PLACEHOLDER", base_value)
        .replace("SWAPPED_VALUE_PLACEHOLDER", normalized_swapped_alias)
    )
