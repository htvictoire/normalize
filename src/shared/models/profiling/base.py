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
    """Base for decimal-family profiles that also detect separator swap."""

    swapped_match_count: int
    swapped_match_ratio: float
    separator_mismatch_detected: bool


class SymbolDistributionProfile(MainModel):
    """Base for currency-family profiles that track currency symbol distribution."""

    symbol_distribution: dict[str, int]
    dominant_symbol: str | None
    dominant_symbol_ratio: float
    has_mixed_symbols: bool
