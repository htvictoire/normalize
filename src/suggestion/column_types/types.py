"""Type inference logic for suggestion sampling."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from suggestion.column_types.numeric.scoring import infer_best_numeric_fits
from suggestion.constants import (
    BOOLEAN_FALSE_TOKENS,
    BOOLEAN_TRUE_TOKENS,
    DATE_FORMAT_CANDIDATES,
    TYPE_MATCH_MIN_RATIO,
)
from suggestion.column_types.models import NumericSuggestion


def infer_column_type(
    values: Sequence[str],
) -> tuple[str, str | None, NumericSuggestion | None]:
    """Infer type, date format, and numeric suggestion for one sampled column."""
    sample_count = len(values)
    if sample_count == 0:
        return "string", None, None

    boolean_matches = sum(1 for value in values if is_boolean(value))
    integer_fit, decimal_fit, currency_fit = infer_best_numeric_fits(values)
    integer_matches = 0 if integer_fit is None else integer_fit.matches
    decimal_matches = 0 if decimal_fit is None else decimal_fit.matches
    currency_matches = 0 if currency_fit is None else currency_fit.matches

    date_format_counts: dict[str, int] = dict.fromkeys(DATE_FORMAT_CANDIDATES, 0)
    for value in values:
        matched_format = match_date_format(value)
        if matched_format is not None:
            date_format_counts[matched_format] += 1
    best_date_format = max(date_format_counts.items(), key=lambda item: item[1])[0]
    best_date_count = date_format_counts[best_date_format]

    def meets_threshold(matches: int) -> bool:
        return matches / sample_count >= TYPE_MATCH_MIN_RATIO

    inferred_type = "string"
    inferred_date_format: str | None = None
    inferred_numeric_suggestion: NumericSuggestion | None = None

    if meets_threshold(boolean_matches):
        inferred_type = "boolean"
    elif meets_threshold(integer_matches) and integer_fit is not None:
        inferred_type = "integer"
        inferred_numeric_suggestion = integer_fit.suggestion
    elif meets_threshold(currency_matches) and currency_fit is not None:
        inferred_type = "currency"
        inferred_numeric_suggestion = currency_fit.suggestion
    elif meets_threshold(decimal_matches) and decimal_fit is not None:
        inferred_type = "decimal"
        inferred_numeric_suggestion = decimal_fit.suggestion
    elif meets_threshold(best_date_count):
        inferred_type = "date"
        inferred_date_format = best_date_format

    return inferred_type, inferred_date_format, inferred_numeric_suggestion


def is_boolean(value: str) -> bool:
    """Return True when value is a recognised boolean token."""
    normalized = value.strip().lower()
    return normalized in BOOLEAN_TRUE_TOKENS or normalized in BOOLEAN_FALSE_TOKENS


def match_date_format(value: str) -> str | None:
    """Return the first supported date format that parses the given value."""
    for date_format in DATE_FORMAT_CANDIDATES:
        try:
            datetime.strptime(value, date_format)
        except ValueError:
            continue
        return date_format
    return None
