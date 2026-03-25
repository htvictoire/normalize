"""Per-column type inference: maps sampled string values to a ColumnConfig."""

from __future__ import annotations

from collections.abc import Sequence

from shared.models.column import (
    BooleanColumnConfig,
    ColumnConfig,
    DateColumnConfig,
    StringColumnConfig,
)
from suggestion.column_config.boolean import is_boolean
from suggestion.column_config.date import best_date_format
from suggestion.column_config.numeric import infer_numeric_type
from suggestion.constants import BOOLEAN_TOKEN_PAIRS, TYPE_MATCH_MIN_RATIO


def infer_column_type(values: Sequence[str]) -> ColumnConfig:
    """Infer and return a ColumnConfig for one sampled column."""
    if not values:
        return StringColumnConfig()

    sample_count = len(values)

    def meets_threshold(matches: int) -> bool:
        return matches / sample_count >= TYPE_MATCH_MIN_RATIO

    boolean_matches = [v.strip().lower() for v in values if is_boolean(v)]
    if meets_threshold(len(boolean_matches)):
        observed_boolean_tokens = set(boolean_matches)
        active_pairs = [
            (t, f)
            for t, f in BOOLEAN_TOKEN_PAIRS
            if t in observed_boolean_tokens or f in observed_boolean_tokens
        ]
        true_tokens = tuple(sorted(t for t, _ in active_pairs))
        false_tokens = tuple(sorted(f for _, f in active_pairs))
        return BooleanColumnConfig(true_tokens=true_tokens, false_tokens=false_tokens)

    numeric = infer_numeric_type(values, sample_count)
    if numeric is not None:
        return numeric

    date_format, date_count = best_date_format(values)
    if date_format is not None and meets_threshold(date_count):
        return DateColumnConfig(date_format=date_format)

    return StringColumnConfig()
