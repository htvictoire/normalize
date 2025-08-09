"""Type inference logic for suggestion sampling."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from suggest.constants import BOOLEAN_FALSE_TOKENS, BOOLEAN_TRUE_TOKENS, DATE_FORMAT_CANDIDATES
from suggest.inference.numeric.scoring import infer_best_numeric_fits
from suggest.models import NumericSuggestion


def infer_column_type(
    values: Sequence[str],
) -> tuple[str, str | None, NumericSuggestion | None]:
    """Infer type/date format/numeric suggestion for one sampled column."""
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

    inferred_type = "string"
    inferred_date_format: str | None = None
    inferred_numeric: NumericSuggestion | None = None
    if boolean_matches == sample_count:
        inferred_type = "boolean"
    elif integer_matches == sample_count and integer_fit is not None:
        inferred_type = "integer"
        inferred_numeric = integer_fit.suggestion
    elif currency_matches == sample_count and currency_fit is not None:
        inferred_type = "currency"
        inferred_numeric = currency_fit.suggestion
    elif decimal_matches == sample_count and decimal_fit is not None:
        inferred_type = "decimal"
        inferred_numeric = decimal_fit.suggestion
    elif best_date_count == sample_count:
        inferred_type = "date"
        inferred_date_format = best_date_format
    else:
        ranked: list[tuple[str, int]] = [
            ("boolean", boolean_matches),
            ("integer", integer_matches),
            ("currency", currency_matches),
            ("decimal", decimal_matches),
            ("date", best_date_count),
        ]
        top_type, top_score = max(ranked, key=lambda item: item[1])
        if top_score > 0:
            if top_type == "date":
                inferred_type = "date"
                inferred_date_format = best_date_format
            elif top_type == "integer" and integer_fit is not None:
                inferred_type = "integer"
                inferred_numeric = integer_fit.suggestion
            elif top_type == "decimal" and decimal_fit is not None:
                inferred_type = "decimal"
                inferred_numeric = decimal_fit.suggestion
            elif top_type == "currency" and currency_fit is not None:
                inferred_type = "currency"
                inferred_numeric = currency_fit.suggestion
            elif top_type == "boolean":
                inferred_type = "boolean"
    return inferred_type, inferred_date_format, inferred_numeric


def is_boolean(value: str) -> bool:
    """Return True when value is one of the supported boolean tokens."""
    normalized = value.strip().lower()
    return normalized in BOOLEAN_TRUE_TOKENS or normalized in BOOLEAN_FALSE_TOKENS


def match_date_format(value: str) -> str | None:
    """Try supported date formats and return the first matching format."""
    for date_format in DATE_FORMAT_CANDIDATES:
        try:
            datetime.strptime(value, date_format)
        except ValueError:
            continue
        return date_format
    return None
