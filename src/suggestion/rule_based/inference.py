"""Per-column type inference: maps sampled string values to a ColumnConfig."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from shared.models.column import (
    BooleanColumnConfig,
    ColumnConfig,
    DateColumnConfig,
    DateTimeColumnConfig,
    StringColumnConfig,
    TimeColumnConfig,
)

from suggestion.rule_based.boolean import is_boolean
from suggestion.rule_based.constants import BOOLEAN_TOKEN_PAIRS, TYPE_MATCH_MIN_RATIO
from suggestion.rule_based.date import (
    best_date_format,
    best_datetime_format,
    best_time_format,
)
from suggestion.rule_based.numeric import infer_numeric_type


def _infer_temporal_type(
    values: Sequence[str],
    meets_threshold: Callable[[int], bool],
) -> ColumnConfig | None:
    datetime_format, datetime_count = best_datetime_format(values)
    if datetime_format is not None and meets_threshold(datetime_count):
        return DateTimeColumnConfig(datetime_format=datetime_format)

    time_format, time_count = best_time_format(values)
    if time_format is not None and meets_threshold(time_count):
        return TimeColumnConfig(time_format=time_format)

    date_format, date_count = best_date_format(values)
    if date_format is not None and meets_threshold(date_count):
        return DateColumnConfig(date_format=date_format)

    return None


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

    temporal = _infer_temporal_type(values, meets_threshold)
    if temporal is not None:
        return temporal

    return StringColumnConfig()
