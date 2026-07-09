"""Numeric candidate scoring and best-fit selection."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from suggestion.rule_based.constants import LEADING_DECIMAL_MIN_RATIO, NUMERIC_CANDIDATES
from suggestion.rule_based.models import (
    NumericCandidate,
    NumericCandidateStats,
    NumericFits,
    NumericTypeFit,
)
from suggestion.rule_based.numeric.parsing import parse_numeric_token


def _fit_key(fit: NumericTypeFit) -> tuple[int, int, int, int]:
    return (fit.matches, fit.separator_evidence, fit.grouping_evidence, -fit.rank)


def _score_candidate(
    values: Sequence[str],
    candidate: NumericCandidate,
) -> NumericCandidateStats:
    """Count how many values parse as integer/decimal/currency under one candidate format."""
    integer_matches = 0
    decimal_matches = 0
    currency_matches = 0
    accounting_matches = 0
    signed_matches = 0
    percentage_matches = 0
    separator_evidence = 0
    grouping_evidence = 0
    leading_decimal_matches = 0

    for value in values:
        parsed = parse_numeric_token(value, candidate)
        if parsed is None:
            continue
        if parsed.used_decimal_separator or parsed.used_thousand_separator:
            separator_evidence += 1
        if parsed.used_thousand_separator:
            grouping_evidence += 1
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

    return NumericCandidateStats(
        integer_matches=integer_matches,
        decimal_matches=decimal_matches,
        currency_matches=currency_matches,
        accounting_matches=accounting_matches,
        signed_matches=signed_matches,
        percentage_matches=percentage_matches,
        separator_evidence=separator_evidence,
        grouping_evidence=grouping_evidence,
        leading_decimal_matches=leading_decimal_matches,
    )


def _candidate_fits(
    values: Sequence[str],
    total: int,
    rank: int,
    candidate: NumericCandidate,
) -> NumericFits:
    stats = _score_candidate(values, candidate)
    allow_leading = total > 0 and stats.leading_decimal_matches / total >= LEADING_DECIMAL_MIN_RATIO
    base = NumericTypeFit(
        matches=0,
        separator_evidence=stats.separator_evidence,
        grouping_evidence=stats.grouping_evidence,
        rank=rank,
        candidate=candidate,
        allow_leading_decimal_point=allow_leading,
    )
    return NumericFits(
        integer=replace(base, matches=stats.integer_matches),
        decimal=replace(base, matches=stats.decimal_matches),
        currency=replace(base, matches=stats.currency_matches),
        accounting=replace(base, matches=stats.accounting_matches),
        percentage=replace(base, matches=stats.percentage_matches),
        signed=replace(base, matches=stats.signed_matches),
    )


def infer_best_numeric_fits(values: Sequence[str]) -> NumericFits:
    """Return best integer/decimal/currency/accounting/percentage/signed fit."""
    total = len(values)
    all_fits = [
        _candidate_fits(values, total, rank, candidate)
        for rank, candidate in enumerate(NUMERIC_CANDIDATES)
    ]
    return NumericFits(
        integer=max((f.integer for f in all_fits), key=_fit_key),
        decimal=max((f.decimal for f in all_fits), key=_fit_key),
        currency=max((f.currency for f in all_fits), key=_fit_key),
        accounting=max((f.accounting for f in all_fits), key=_fit_key),
        percentage=max((f.percentage for f in all_fits), key=_fit_key),
        signed=max((f.signed for f in all_fits), key=_fit_key),
    )
