"""Profiling base classes: counts and profile capability bases."""

from __future__ import annotations

from dataclasses import dataclass

from shared.models.base import MainModel


class ColumnCounts(MainModel):
    null_count: int           # structural: SQL NULL + empty/whitespace
    nullish_count: int        # semantic: structural + null token matches
    non_null_count: int       # row_count - null_count
    non_nullish_count: int    # row_count - nullish_count


@dataclass(frozen=True)
class ColumnCountResult:
    """Row count and per-column null/nullish counts from a single table scan."""

    row_count: int
    column_counts: dict[str, ColumnCounts]


class ParseMatchProfile(MainModel):
    """Base for profiles that measure how many values match the declared format."""

    parse_match_count: int
    parse_match_ratio: float


class SeparatorMismatchProfile(ParseMatchProfile):
    """Base for decimal-style profiles that also detect separator swap."""

    swapped_match_count: int
    swapped_match_ratio: float
    separator_mismatch_detected: bool


class DecimalStatsProfile(SeparatorMismatchProfile):
    """Base for decimal/percentage/signed profiles with identical parse stats."""


class SymbolDistributionProfile(MainModel):
    """Base for monetary profiles that track currency symbol distribution."""

    symbol_distribution: dict[str, int]
    symbol_detected_count: int
    symbol_detected_ratio: float
    missing_symbol_count: int
    missing_symbol_ratio: float
    dominant_symbol: str | None
    dominant_symbol_ratio: float
    has_mixed_symbols: bool


class MonetaryProfile(SymbolDistributionProfile, SeparatorMismatchProfile):
    """Base for monetary profiles that share symbol coverage and parse stats."""


class CurrencyFormatProfile(MainModel):
    """Base for currency profiles that track monetary token formatting consistency."""

    symbol_position_distribution: dict[str, int]
    dominant_symbol_position: str | None
    dominant_symbol_position_ratio: float
    has_mixed_symbol_positions: bool
    currency_token_form_distribution: dict[str, int]
    dominant_currency_token_form: str | None
    dominant_currency_token_form_ratio: float
    has_mixed_currency_token_forms: bool


class AccountingSignProfile(MainModel):
    """Base for accounting profiles that track sign-notation behavior."""

    sign_notation_distribution: dict[str, int]
    dominant_sign_notation: str | None
    dominant_sign_notation_ratio: float
    has_mixed_sign_notations: bool
    negative_marker_distribution: dict[str, int]
    positive_marker_distribution: dict[str, int]
    parentheses_negative_count: int
    leading_sign_count: int
    trailing_sign_count: int
    explicit_sign_count: int
    unsigned_non_nullish_count: int
