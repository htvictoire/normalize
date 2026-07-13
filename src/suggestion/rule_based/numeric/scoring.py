"""Numeric type scoring.

Values no longer need to be scored against candidate separator layouts: each value
resolves its own locale, so one pass classifies the column's numeric family.
"""

from __future__ import annotations

from collections.abc import Sequence

from suggestion.rule_based.constants import LEADING_DECIMAL_MIN_RATIO
from suggestion.rule_based.models import NumericFits, NumericStats, NumericTypeFit
from suggestion.rule_based.numeric.parsing import parse_numeric_token


def _score_values(values: Sequence[str]) -> NumericStats:
    """Count how many values parse as each numeric family."""
    integer_matches = 0
    decimal_matches = 0
    currency_matches = 0
    accounting_matches = 0
    signed_matches = 0
    percentage_matches = 0
    leading_decimal_matches = 0

    for value in values:
        parsed = parse_numeric_token(value)
        if parsed is None:
            continue
        if parsed.leading_decimal_point:
            leading_decimal_matches += 1
        if parsed.has_signed and parsed.has_currency:
            accounting_matches += 1
        elif parsed.has_signed:
            signed_matches += 1
        elif parsed.has_currency:
            currency_matches += 1
        elif parsed.has_percentage:
            percentage_matches += 1
        elif parsed.has_fractional_part:
            decimal_matches += 1
        else:
            integer_matches += 1

    return NumericStats(
        integer_matches=integer_matches,
        decimal_matches=decimal_matches,
        currency_matches=currency_matches,
        accounting_matches=accounting_matches,
        signed_matches=signed_matches,
        percentage_matches=percentage_matches,
        leading_decimal_matches=leading_decimal_matches,
    )


def infer_best_numeric_fits(values: Sequence[str]) -> NumericFits:
    """Return the integer/decimal/currency/accounting/percentage/signed fits."""
    total = len(values)
    stats = _score_values(values)
    allow_leading = total > 0 and stats.leading_decimal_matches / total >= LEADING_DECIMAL_MIN_RATIO

    def fit(matches: int) -> NumericTypeFit:
        return NumericTypeFit(matches=matches, allow_leading_decimal_point=allow_leading)

    return NumericFits(
        integer=fit(stats.integer_matches),
        decimal=fit(stats.decimal_matches),
        currency=fit(stats.currency_matches),
        accounting=fit(stats.accounting_matches),
        percentage=fit(stats.percentage_matches),
        signed=fit(stats.signed_matches),
    )
