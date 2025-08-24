"""Suggestion-domain internal inference models."""

from __future__ import annotations

from dataclasses import dataclass

from shared.models.column import GroupingStyle


@dataclass(frozen=True)
class NumericCandidate:
    """One candidate numeric formatting layout."""

    decimal_separator: str
    thousand_separator: str
    grouping_style: GroupingStyle


@dataclass(frozen=True)
class NumericParseResult:
    """Parsed numeric token and parsing evidence."""

    normalized: str
    has_currency: bool
    used_decimal_separator: bool
    used_thousand_separator: bool
    leading_decimal_point: bool


@dataclass(frozen=True)
class NumericCandidateStats:
    """Per-candidate match counts gathered from sampled values."""

    integer_matches: int
    decimal_matches: int
    currency_matches: int
    separator_evidence: int
    grouping_evidence: int
    leading_decimal_matches: int


@dataclass(frozen=True)
class NumericTypeFit:
    """Best fit for one numeric family (integer/decimal/currency)."""

    matches: int
    separator_evidence: int
    grouping_evidence: int
    rank: int
    candidate: NumericCandidate
    allow_leading_decimal_point: bool
