"""Numeric type decision: maps scored fits to a concrete ColumnConfig."""

from __future__ import annotations

from collections.abc import Sequence

from shared.models.column import (
    AccountingColumnConfig,
    ColumnConfig,
    CurrencyColumnConfig,
    DecimalColumnConfig,
    IntegerColumnConfig,
    PercentageColumnConfig,
    SignedColumnConfig,
)
from shared.parsing.currency import CURRENCY_DETECTION_RE
from shared.parsing.markers import POSITIVE_SIGN_MARKERS, SIGN_MARKER_DETECTION_RE
from suggestion.column_config.numeric.scoring import infer_best_numeric_fits
from suggestion.constants import (
    CURRENCY_MATCH_MIN_RATIO,
    SIGNED_MATCH_MIN_RATIO,
    TYPE_MATCH_MIN_RATIO,
)
from suggestion.models import NumericFits


def infer_numeric_type(values: Sequence[str], sample_count: int) -> ColumnConfig | None:
    """Return the best-fit numeric ColumnConfig, or None if no numeric type fits."""
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
    if fits.signed.matches / sample_count >= SIGNED_MATCH_MIN_RATIO:
        c = fits.signed.candidate
        negative_markers, positive_markers, parentheses_as_negative = _detect_signed_markers(values)
        if any(CURRENCY_DETECTION_RE.search(v) for v in values):
            return AccountingColumnConfig(
                decimal_separator=c.decimal_separator,
                thousand_separator=c.thousand_separator,
                grouping_style=c.grouping_style,
                allow_leading_decimal_point=fits.signed.allow_leading_decimal_point,
                positive_markers=positive_markers,
                negative_markers=negative_markers,
                parentheses_as_negative=parentheses_as_negative,
            )
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


def _detect_signed_markers(
    values: Sequence[str],
) -> tuple[tuple[str, ...], tuple[str, ...], bool]:
    """Scan sample values to find which sign markers and notations are present."""
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
