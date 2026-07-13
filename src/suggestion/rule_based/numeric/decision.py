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

from suggestion.rule_based.constants import (
    CURRENCY_MATCH_MIN_RATIO,
    SIGNED_MATCH_MIN_RATIO,
    TYPE_MATCH_MIN_RATIO,
)
from suggestion.rule_based.models import NumericFits, SignedMarkers
from suggestion.rule_based.numeric.scoring import infer_best_numeric_fits


def infer_numeric_type(values: Sequence[str], sample_count: int) -> ColumnConfig | None:
    """Return the best-fit numeric ColumnConfig, or None if no numeric type fits."""
    fits = infer_best_numeric_fits(values)
    if fits.integer / sample_count >= TYPE_MATCH_MIN_RATIO:
        return IntegerColumnConfig()
    currency_like = _infer_currency_like(values, sample_count, fits)
    if currency_like is not None:
        return currency_like
    if fits.percentage / sample_count >= TYPE_MATCH_MIN_RATIO:
        return PercentageColumnConfig()
    if fits.decimal / sample_count >= TYPE_MATCH_MIN_RATIO:
        return DecimalColumnConfig()
    return None


def _infer_currency_like(
    values: Sequence[str],
    sample_count: int,
    fits: NumericFits,
) -> ColumnConfig | None:
    if fits.accounting / sample_count >= CURRENCY_MATCH_MIN_RATIO:
        markers = _detect_signed_markers(values)
        return AccountingColumnConfig(
            positive_markers=markers.positive,
            negative_markers=markers.negative,
            parentheses_as_negative=markers.parentheses_as_negative,
        )
    if fits.signed / sample_count >= SIGNED_MATCH_MIN_RATIO:
        markers = _detect_signed_markers(values)
        if any(CURRENCY_DETECTION_RE.search(v) for v in values):
            return AccountingColumnConfig(
                positive_markers=markers.positive,
                negative_markers=markers.negative,
                parentheses_as_negative=markers.parentheses_as_negative,
            )
        return SignedColumnConfig(
            positive_markers=markers.positive,
            negative_markers=markers.negative,
            parentheses_as_negative=markers.parentheses_as_negative,
        )
    if fits.currency / sample_count >= CURRENCY_MATCH_MIN_RATIO:
        return CurrencyColumnConfig()
    return None


def _detect_signed_markers(
    values: Sequence[str],
) -> SignedMarkers:
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
    return SignedMarkers(
        negative=tuple(sorted(found_negative)),
        positive=tuple(sorted(found_positive)),
        parentheses_as_negative=has_parens,
    )
