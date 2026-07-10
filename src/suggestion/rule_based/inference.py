"""Per-column type inference: maps sampled string values to a ColumnConfig."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from shared.models.column import (
    BooleanColumnConfig,
    ColumnConfig,
    DateColumnConfig,
    DateTimeColumnConfig,
    StringColumnConfig,
    TimeColumnConfig,
)

from suggestion.rule_based.boolean import is_boolean
from suggestion.rule_based.code import infer_code_type
from suggestion.rule_based.constants import BOOLEAN_TOKEN_PAIRS, TYPE_MATCH_MIN_RATIO
from suggestion.rule_based.date import (
    best_date_format,
    best_datetime_format,
    best_time_format,
)
from suggestion.rule_based.identifier import infer_identifier_type
from suggestion.rule_based.numeric import infer_numeric_type


@dataclass(frozen=True)
class ColumnInference:
    config: ColumnConfig
    confidence: float


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


def infer_column_type(
    values: Sequence[str],
    extended_type_detection: bool,
    column_name: str = "",
) -> ColumnConfig:
    """Infer and return a ColumnConfig for one sampled column."""
    return infer_column(values, extended_type_detection, column_name).config


def infer_column(
    values: Sequence[str],
    extended_type_detection: bool,
    column_name: str = "",
) -> ColumnInference:
    """Infer one sampled column's config and confidence."""
    if not values:
        return ColumnInference(StringColumnConfig(), 1.0)

    sample_count = len(values)
    value_list = list(values)
    result: ColumnConfig | None = None
    confidence = 1.0

    identifier = infer_identifier_type(column_name, value_list)
    if identifier is not None:
        result = identifier.config
        confidence = identifier.confidence
    else:

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
            result = BooleanColumnConfig(true_tokens=true_tokens, false_tokens=false_tokens)
        else:
            numeric = infer_numeric_type(values, sample_count)
            result = numeric

        if result is None:
            result = _infer_temporal_type(values, meets_threshold)

        if result is None and extended_type_detection:
            result = infer_code_type(values, sample_count)

    return ColumnInference(result or StringColumnConfig(), confidence)
