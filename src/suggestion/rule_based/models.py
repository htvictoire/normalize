"""Internal models for the rule-based numeric inference scorer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NumericParseResult:
    """Parsed numeric token and parsing evidence."""

    normalized: str
    has_currency: bool
    has_signed: bool
    has_percentage: bool
    has_fractional_part: bool


@dataclass(frozen=True)
class NumericStats:
    """Match counts gathered from sampled values."""

    integer_matches: int
    decimal_matches: int
    currency_matches: int
    accounting_matches: int
    signed_matches: int
    percentage_matches: int


@dataclass(frozen=True)
class NumericFits:
    """Match count for each numeric type family."""

    integer: int
    decimal: int
    currency: int
    accounting: int
    percentage: int
    signed: int
