"""Numeric type scoring.

Values no longer need to be scored against candidate separator layouts: each value
resolves its own locale, so one pass classifies the column's numeric family.
"""

from __future__ import annotations

from collections.abc import Sequence

from suggestion.rule_based.models import NumericFits, NumericStats
from suggestion.rule_based.numeric.parsing import parse_numeric_token


def _score_values(values: Sequence[str]) -> NumericStats:
    """Count how many values parse as each numeric family."""
    integer_matches = 0
    decimal_matches = 0
    currency_matches = 0
    accounting_matches = 0
    signed_matches = 0
    percentage_matches = 0

    for value in values:
        parsed = parse_numeric_token(value)
        if parsed is None:
            continue
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
    )


def infer_best_numeric_fits(values: Sequence[str]) -> NumericFits:
    """Return the integer/decimal/currency/accounting/percentage/signed match counts."""
    stats = _score_values(values)
    return NumericFits(
        integer=stats.integer_matches,
        decimal=stats.decimal_matches,
        currency=stats.currency_matches,
        accounting=stats.accounting_matches,
        percentage=stats.percentage_matches,
        signed=stats.signed_matches,
    )
