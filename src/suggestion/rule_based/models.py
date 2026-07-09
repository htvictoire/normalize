"""Internal models for the rule-based numeric inference scorer."""

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
    has_signed: bool
    has_percentage: bool
    has_fractional_part: bool
    used_decimal_separator: bool
    used_thousand_separator: bool
    leading_decimal_point: bool


@dataclass(frozen=True)
class NumericCandidateStats:
    """Per-candidate match counts gathered from sampled values."""

    integer_matches: int
    decimal_matches: int
    currency_matches: int
    accounting_matches: int
    signed_matches: int
    percentage_matches: int
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


@dataclass(frozen=True)
class SignedMarkers:
    """Sign markers detected in sampled numeric values."""

    negative: tuple[str, ...]
    positive: tuple[str, ...]
    parentheses_as_negative: bool


@dataclass(frozen=True)
class NumericFits:
    """Best-fit result for each numeric type family."""

    integer: NumericTypeFit
    decimal: NumericTypeFit
    currency: NumericTypeFit
    accounting: NumericTypeFit
    percentage: NumericTypeFit
    signed: NumericTypeFit
