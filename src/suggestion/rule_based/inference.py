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
    NUMERIC_BOOLEAN_TOKENS,
    TYPE_MATCH_MIN_RATIO,
)
from suggestion.rule_based.date import (
    count_time_matches,
    infer_date_day_first,
    infer_datetime_day_first,
)
from suggestion.rule_based.identifier import infer_identifier_type
from suggestion.rule_based.numeric import infer_numeric_type


def _infer_temporal_type(
    values: Sequence[str],
    meets_threshold: Callable[[int], bool],
) -> ColumnConfig | None:
    datetime_day_first, datetime_count = infer_datetime_day_first(values)
    if meets_threshold(datetime_count):
        return DateTimeColumnConfig(day_first=datetime_day_first)

    time_count = count_time_matches(values)
    if meets_threshold(time_count):
        return TimeColumnConfig()

    date_day_first, date_count = infer_date_day_first(values)
    if meets_threshold(date_count):
        return DateColumnConfig(day_first=date_day_first)

    return None


def _infer_boolean_type(observed_tokens: set[str]) -> BooleanColumnConfig | None:
    """Decide whether a column of boolean tokens is a boolean column.

    Returns None unless an observed token is non-numeric. `0` and `1` are equally an
    integer, and boolean is tested before numeric, so numeric-only evidence would claim
    identifier and quantity columns. A boolean written solely as `0`/`1` therefore types
    as integer: lossless, and correctable at confirmation.
    """
    if observed_tokens <= NUMERIC_BOOLEAN_TOKENS:
        return None
    return BooleanColumnConfig()


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
