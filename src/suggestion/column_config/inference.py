"""Per-column type inference: maps sampled string values to a ColumnConfig."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from shared.models.column import (
    AccountingColumnConfig,
    BooleanColumnConfig,
    ColumnConfig,
    CurrencyColumnConfig,
    DateColumnConfig,
    DecimalColumnConfig,
    IntegerColumnConfig,
    PercentageColumnConfig,
    SignedColumnConfig,
    StringColumnConfig,
)
from shared.utils.currency import CURRENCY_DETECTION_RE
from shared.utils.sign_markers import (
    POSITIVE_SIGN_MARKERS,
    SIGN_MARKER_DETECTION_RE,
)
from suggestion.column_config.models import NumericFits
from suggestion.column_config.numeric.scoring import infer_best_numeric_fits
from suggestion.constants import (
    BOOLEAN_FALSE_TOKENS,
    BOOLEAN_TOKEN_PAIRS,
    BOOLEAN_TRUE_TOKENS,
    CURRENCY_MATCH_MIN_RATIO,
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


def _detect_signed_markers(
    values: Sequence[str],
) -> tuple[tuple[str, ...], tuple[str, ...], bool]:
    """Scan sample to find which sign markers and notations are present."""
    found_negative: set[str] = set()
    found_positive: set[str] = set()
    has_parens = False
    for value in values:
        clean = CURRENCY_DETECTION_RE.sub("", value).strip()
        m = SIGN_MARKER_DETECTION_RE.search(clean)
        if m:
            token = m.group(1).upper()
            if token in POSITIVE_SIGN_MARKERS:
                found_positive.add(token)
            else:
                found_negative.add(token)
        stripped = clean.strip()
        if not has_parens and stripped.startswith("(") and stripped.endswith(")"):
            has_parens = True
    return tuple(sorted(found_negative)), tuple(sorted(found_positive)), has_parens


def _infer_currency_like(
    values: Sequence[str],
    sample_count: int,
    fits: NumericFits,
) -> ColumnConfig | None:
    if fits.accounting.matches / sample_count >= CURRENCY_MATCH_MIN_RATIO:
        c = fits.accounting.candidate
        negative_markers, positive_markers, parentheses_as_negative = _detect_signed_markers(values)
        return AccountingColumnConfig(
            decimal_separator=c.decimal_separator,
            thousand_separator=c.thousand_separator,
            grouping_style=c.grouping_style,
            allow_leading_decimal_point=fits.accounting.allow_leading_decimal_point,
            positive_markers=positive_markers,
            negative_markers=negative_markers,
            parentheses_as_negative=parentheses_as_negative,
        )
    if fits.signed.matches / sample_count >= CURRENCY_MATCH_MIN_RATIO:
        c = fits.signed.candidate
        negative_markers, positive_markers, parentheses_as_negative = _detect_signed_markers(values)
        return SignedColumnConfig(
            decimal_separator=c.decimal_separator,
            thousand_separator=c.thousand_separator,
            grouping_style=c.grouping_style,
            allow_leading_decimal_point=fits.signed.allow_leading_decimal_point,
            positive_markers=positive_markers,
            negative_markers=negative_markers,
            parentheses_as_negative=parentheses_as_negative,
        )
    if fits.currency.matches / sample_count >= CURRENCY_MATCH_MIN_RATIO:
        c = fits.currency.candidate
        return CurrencyColumnConfig(
            decimal_separator=c.decimal_separator,
            thousand_separator=c.thousand_separator,
            grouping_style=c.grouping_style,
            allow_leading_decimal_point=fits.currency.allow_leading_decimal_point,
        )
    return None


def _infer_numeric(values: Sequence[str], sample_count: int) -> ColumnConfig | None:
    fits = infer_best_numeric_fits(values)
    if fits.integer.matches / sample_count >= TYPE_MATCH_MIN_RATIO:
        c = fits.integer.candidate
        return IntegerColumnConfig(
            thousand_separator=c.thousand_separator,
            grouping_style=c.grouping_style,
        )
    currency_like = _infer_currency_like(values, sample_count, fits)
    if currency_like is not None:
        return currency_like
    if fits.percentage.matches / sample_count >= TYPE_MATCH_MIN_RATIO:
        c = fits.percentage.candidate
        return PercentageColumnConfig(
            decimal_separator=c.decimal_separator,
            thousand_separator=c.thousand_separator,
            grouping_style=c.grouping_style,
            allow_leading_decimal_point=fits.percentage.allow_leading_decimal_point,
        )
    if fits.decimal.matches / sample_count >= TYPE_MATCH_MIN_RATIO:
        c = fits.decimal.candidate
        return DecimalColumnConfig(
            decimal_separator=c.decimal_separator,
            thousand_separator=c.thousand_separator,
            grouping_style=c.grouping_style,
            allow_leading_decimal_point=fits.decimal.allow_leading_decimal_point,
        )
    return None


def infer_column_type(values: Sequence[str]) -> ColumnConfig:
    """Infer and return a ColumnConfig for one sampled column."""
    if not values:
        return StringColumnConfig()

    sample_count = len(values)

    def meets_threshold(matches: int) -> bool:
        return matches / sample_count >= TYPE_MATCH_MIN_RATIO

    boolean_normalized = {v.strip().lower() for v in values if _is_boolean(v)}
    if meets_threshold(len(boolean_normalized)):
        active_pairs = [
            (t, f)
            for t, f in BOOLEAN_TOKEN_PAIRS
            if t in boolean_normalized or f in boolean_normalized
        ]
        true_tokens = tuple(sorted(t for t, _ in active_pairs))
        false_tokens = tuple(sorted(f for _, f in active_pairs))
        return BooleanColumnConfig(true_tokens=true_tokens, false_tokens=false_tokens)

    numeric = _infer_numeric(values, sample_count)
    if numeric is not None:
        return numeric

    date_format, date_count = _best_date_format(values)
    if date_format is not None and meets_threshold(date_count):
        return DateColumnConfig(date_format=date_format)

    return StringColumnConfig()
