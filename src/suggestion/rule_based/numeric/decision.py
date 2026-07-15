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

from suggestion.rule_based.constants import (
    CURRENCY_MATCH_MIN_RATIO,
    SIGNED_MATCH_MIN_RATIO,
    TYPE_MATCH_MIN_RATIO,
)
from suggestion.rule_based.models import NumericFits
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
        return AccountingColumnConfig()
    if fits.signed / sample_count >= SIGNED_MATCH_MIN_RATIO:
        if any(CURRENCY_DETECTION_RE.search(v) for v in values):
            return AccountingColumnConfig()
        return SignedColumnConfig()
    if fits.currency / sample_count >= CURRENCY_MATCH_MIN_RATIO:
        return CurrencyColumnConfig()
    return None
