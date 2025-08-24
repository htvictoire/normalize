"""Numeric candidate scoring and best-fit selection."""

from __future__ import annotations

from collections.abc import Sequence

from suggestion.column_config.models import (
    NumericCandidate,
    NumericCandidateStats,
    NumericTypeFit,
)
from suggestion.column_config.numeric.parsing import parse_numeric_token
from suggestion.constants import LEADING_DECIMAL_MIN_RATIO, NUMERIC_CANDIDATES


def _keep_better(
    current: NumericTypeFit | None,
    candidate: NumericTypeFit,
) -> NumericTypeFit:
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
    return candidate if candidate_score > current_score else current


def _score_candidate(
    values: Sequence[str],
    candidate: NumericCandidate,
) -> NumericCandidateStats:
    """Count how many values parse as integer/decimal/currency under one candidate format."""
    integer_matches = 0
    decimal_matches = 0
    currency_matches = 0
    separator_evidence = 0
    grouping_evidence = 0
    leading_decimal_matches = 0

    for value in values:
        parsed = parse_numeric_token(value, candidate=candidate)
        if parsed is None:
            continue
        if parsed.used_decimal_separator or parsed.used_thousand_separator:
            separator_evidence += 1
        if parsed.used_thousand_separator:
            grouping_evidence += 1
        if parsed.leading_decimal_point:
            leading_decimal_matches += 1
        if parsed.has_currency:
            currency_matches += 1
        elif "." in parsed.normalized:
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


def infer_best_numeric_fits(
    values: Sequence[str],
) -> tuple[NumericTypeFit, NumericTypeFit, NumericTypeFit]:
    """Return best integer/decimal/currency fit across all numeric candidates."""
    best_integer: NumericTypeFit | None = None
    best_decimal: NumericTypeFit | None = None
    best_currency: NumericTypeFit | None = None

    total = len(values)
    for rank, candidate in enumerate(NUMERIC_CANDIDATES):
        stats = _score_candidate(values, candidate)
        allow_leading_decimal_point = (
            total > 0
            and stats.leading_decimal_matches / total >= LEADING_DECIMAL_MIN_RATIO
        )
        best_integer = _keep_better(best_integer, NumericTypeFit(
            matches=stats.integer_matches,
            separator_evidence=stats.separator_evidence,
            grouping_evidence=stats.grouping_evidence,
            rank=rank,
            candidate=candidate,
            allow_leading_decimal_point=allow_leading_decimal_point,
        ))
        best_decimal = _keep_better(best_decimal, NumericTypeFit(
            matches=stats.decimal_matches,
            separator_evidence=stats.separator_evidence,
            grouping_evidence=stats.grouping_evidence,
            rank=rank,
            candidate=candidate,
            allow_leading_decimal_point=allow_leading_decimal_point,
        ))
        best_currency = _keep_better(best_currency, NumericTypeFit(
            matches=stats.currency_matches,
            separator_evidence=stats.separator_evidence,
            grouping_evidence=stats.grouping_evidence,
            rank=rank,
            candidate=candidate,
            allow_leading_decimal_point=allow_leading_decimal_point,
        ))

    if best_integer is None or best_decimal is None or best_currency is None:
        raise RuntimeError("NUMERIC_CANDIDATES is empty")  # pragma: no cover
    return best_integer, best_decimal, best_currency
