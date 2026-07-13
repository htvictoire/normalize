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
from suggestion.rule_based.code import infer_code_type
from suggestion.rule_based.constants import (
    BOOLEAN_TOKEN_PAIRS,
    NUMERIC_BOOLEAN_TOKENS,
    TYPE_MATCH_MIN_RATIO,
)
from suggestion.rule_based.date import (
    best_date_format,
    best_datetime_format,
    best_time_format,
)
from suggestion.rule_based.identifier import infer_identifier_type
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


def _infer_boolean_type(observed_tokens: set[str]) -> BooleanColumnConfig | None:
    """Infer a boolean column from the boolean tokens observed in the sample.

    Returns None unless an observed token is non-numeric. `0` and `1` are equally an
    integer, and boolean is tested before numeric, so numeric-only evidence would claim
    identifier and quantity columns. A boolean written solely as `0`/`1` therefore types
    as integer: lossless, and correctable at confirmation.
    """
    if observed_tokens <= NUMERIC_BOOLEAN_TOKENS:
        return None

    active_pairs = [
        (t, f)
        for t, f in BOOLEAN_TOKEN_PAIRS
        if t in observed_tokens or f in observed_tokens
    ]
    return BooleanColumnConfig(
        true_tokens=tuple(sorted(t for t, _ in active_pairs)),
        false_tokens=tuple(sorted(f for _, f in active_pairs)),
    )


def infer_column_type(
    values: Sequence[str],
    extended_type_detection: bool,
    column_name: str = "",
) -> ColumnConfig:
    """Infer and return a ColumnConfig for one sampled column."""
    if not values:
        return StringColumnConfig()

    sample_count = len(values)

    identifier = infer_identifier_type(column_name, list(values))
    if identifier is not None:
        return identifier.config

    def meets_threshold(matches: int) -> bool:
        return matches / sample_count >= TYPE_MATCH_MIN_RATIO

    result: ColumnConfig | None = None

    boolean_matches = [v.strip().lower() for v in values if is_boolean(v)]
    if meets_threshold(len(boolean_matches)):
        result = _infer_boolean_type(set(boolean_matches))

    if result is None:
        result = infer_numeric_type(values, sample_count)

    if result is None:
        result = _infer_temporal_type(values, meets_threshold)

    if result is None and extended_type_detection:
        result = infer_code_type(values, sample_count)

    return result or StringColumnConfig()
