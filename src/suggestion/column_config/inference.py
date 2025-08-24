"""Per-column type inference: maps sampled string values to a ColumnConfig."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from shared.models.column import (
    BooleanColumnConfig,
    ColumnConfig,
    CurrencyColumnConfig,
    DateColumnConfig,
    DecimalColumnConfig,
    IntegerColumnConfig,
    StringColumnConfig,
)
from suggestion.column_config.numeric.scoring import infer_best_numeric_fits
from suggestion.constants import (
    BOOLEAN_FALSE_TOKENS,
    BOOLEAN_TRUE_TOKENS,
    DATE_FORMAT_CANDIDATES,
    TYPE_MATCH_MIN_RATIO,
)


def _is_boolean(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized in BOOLEAN_TRUE_TOKENS or normalized in BOOLEAN_FALSE_TOKENS


def _match_date_format(value: str) -> str | None:
    for date_format in DATE_FORMAT_CANDIDATES:
        try:
            datetime.strptime(value, date_format)
        except ValueError:
            continue
        return date_format
    return None


def _best_date_format(values: Sequence[str]) -> tuple[str | None, int]:
    counts: dict[str, int] = dict.fromkeys(DATE_FORMAT_CANDIDATES, 0)
    for value in values:
        fmt = _match_date_format(value)
        if fmt is not None:
            counts[fmt] += 1
    best_fmt, best_count = max(counts.items(), key=lambda item: item[1])
    return (best_fmt, best_count) if best_count > 0 else (None, 0)


def _infer_numeric(values: Sequence[str], sample_count: int) -> ColumnConfig | None:
    integer_fit, decimal_fit, currency_fit = infer_best_numeric_fits(values)
    if integer_fit.matches / sample_count >= TYPE_MATCH_MIN_RATIO:
        c = integer_fit.candidate
        return IntegerColumnConfig(
            thousand_separator=c.thousand_separator,
            grouping_style=c.grouping_style,
        )
    if currency_fit.matches / sample_count >= TYPE_MATCH_MIN_RATIO:
        c = currency_fit.candidate
        return CurrencyColumnConfig(
            decimal_separator=c.decimal_separator,
            thousand_separator=c.thousand_separator,
            grouping_style=c.grouping_style,
            allow_leading_decimal_point=currency_fit.allow_leading_decimal_point,
        )
    if decimal_fit.matches / sample_count >= TYPE_MATCH_MIN_RATIO:
        c = decimal_fit.candidate
        return DecimalColumnConfig(
            decimal_separator=c.decimal_separator,
            thousand_separator=c.thousand_separator,
            grouping_style=c.grouping_style,
            allow_leading_decimal_point=decimal_fit.allow_leading_decimal_point,
        )
    return None


def infer_column_type(values: Sequence[str]) -> ColumnConfig:
    """Infer and return a ColumnConfig for one sampled column."""
    if not values:
        return StringColumnConfig()

    sample_count = len(values)

    def meets_threshold(matches: int) -> bool:
        return matches / sample_count >= TYPE_MATCH_MIN_RATIO

    boolean_matches = sum(1 for v in values if _is_boolean(v))
    if meets_threshold(boolean_matches):
        normalized = [v.strip().lower() for v in values]
        true_tokens = tuple(sorted({v for v in normalized if v in BOOLEAN_TRUE_TOKENS}))
        false_tokens = tuple(sorted({v for v in normalized if v in BOOLEAN_FALSE_TOKENS}))
        return BooleanColumnConfig(true_tokens=true_tokens, false_tokens=false_tokens)

    numeric = _infer_numeric(values, sample_count)
    if numeric is not None:
        return numeric

    date_format, date_count = _best_date_format(values)
    if date_format is not None and meets_threshold(date_count):
        return DateColumnConfig(date_format=date_format)

    return StringColumnConfig()
