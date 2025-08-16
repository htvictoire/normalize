"""Numeric candidate scoring and best-fit selection."""

from __future__ import annotations

from collections.abc import Sequence

from suggestion.column_types.numeric.parsing import parse_numeric_token
from suggestion.constants import (
    CURRENCY_RE,
    LEADING_DECIMAL_MIN_RATIO,
    NUMERIC_CANDIDATES,
)
from suggestion.column_types.models import (
    NumericCandidate,
    NumericCandidateStats,
    NumericSuggestion,
    NumericTypeFit,
)


def infer_best_numeric_fits(
    values: Sequence[str],
) -> tuple[NumericTypeFit | None, NumericTypeFit | None, NumericTypeFit | None]:
    """Return best integer/decimal/currency fit across numeric candidates."""
    best_integer: NumericTypeFit | None = None
    best_decimal: NumericTypeFit | None = None
    best_currency: NumericTypeFit | None = None

    total = len(values)
    for rank, candidate in enumerate(NUMERIC_CANDIDATES):
        stats = score_numeric_candidate(values, candidate)
        leading_decimal = (
            total > 0
            and stats.leading_decimal_matches / total >= LEADING_DECIMAL_MIN_RATIO
        )
        suggestion = NumericSuggestion(
            decimal_separator=candidate.decimal_separator,
            thousand_separator=candidate.thousand_separator,
            grouping_style=candidate.grouping_style,
            allow_leading_decimal_point=leading_decimal,
            separator_evidence=stats.separator_evidence,
        )
        integer_fit = NumericTypeFit(
            matches=stats.integer_matches,
            separator_evidence=stats.separator_evidence,
            grouping_evidence=stats.grouping_evidence,
            rank=rank,
            suggestion=suggestion,
        )
        decimal_fit = NumericTypeFit(
            matches=stats.decimal_matches,
            separator_evidence=stats.separator_evidence,
            grouping_evidence=stats.grouping_evidence,
            rank=rank,
            suggestion=suggestion,
        )
        currency_fit = NumericTypeFit(
            matches=stats.currency_matches,
            separator_evidence=stats.separator_evidence,
            grouping_evidence=stats.grouping_evidence,
            rank=rank,
            suggestion=suggestion,
        )
        best_integer = choose_better_numeric_fit(best_integer, integer_fit)
        best_decimal = choose_better_numeric_fit(best_decimal, decimal_fit)
        best_currency = choose_better_numeric_fit(best_currency, currency_fit)

    return best_integer, best_decimal, best_currency


def choose_better_numeric_fit(
    current: NumericTypeFit | None,
    candidate: NumericTypeFit,
) -> NumericTypeFit:
    """Compare two numeric fits and keep the stronger one."""
    if current is None:
        return candidate
    current_score = (
        current.matches,
        current.separator_evidence,
        current.grouping_evidence,
        -current.rank,
    )
    candidate_score = (
        candidate.matches,
        candidate.separator_evidence,
        candidate.grouping_evidence,
        -candidate.rank,
    )
    if candidate_score > current_score:
        return candidate
    return current


def score_numeric_candidate(
    values: Sequence[str],
    candidate: NumericCandidate,
) -> NumericCandidateStats:
    """Score one numeric candidate layout against sampled values."""
    integer_matches = 0
    decimal_matches = 0
    currency_matches = 0
    separator_evidence = 0
    grouping_evidence = 0
    leading_decimal_matches = 0

    for value in values:
        has_currency = CURRENCY_RE.search(value) is not None
        raw_value = CURRENCY_RE.sub("", value) if has_currency else value
        parsed = parse_numeric_token(raw_value, candidate=candidate)
        if parsed is None:
            continue
        if parsed.used_decimal_separator or parsed.used_thousand_separator:
            separator_evidence += 1
        if parsed.used_thousand_separator:
            grouping_evidence += 1
        if parsed.leading_decimal_point:
            leading_decimal_matches += 1

        if has_currency:
            currency_matches += 1
            continue
        if "." in parsed.normalized:
            decimal_matches += 1
        else:
            integer_matches += 1

    return NumericCandidateStats(
        integer_matches=integer_matches,
        decimal_matches=decimal_matches,
        currency_matches=currency_matches,
        separator_evidence=separator_evidence,
        grouping_evidence=grouping_evidence,
        leading_decimal_matches=leading_decimal_matches,
    )
