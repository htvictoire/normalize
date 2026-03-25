"""Profiling models shared across suggestion, profiling, and app layers."""

from __future__ import annotations

from shared.models.base import MainModel
from shared.models.column import ColumnType
from shared.models.issues import NormalizationIssue


class ColumnCounts(MainModel):
    null_count: int           # structural: SQL NULL + empty/whitespace
    nullish_count: int        # semantic: structural + null token matches
    non_null_count: int       # row_count - null_count
    non_nullish_count: int    # row_count - nullish_count


class StringColumnProfile(MainModel):
    distinct_count: int
    distinct_ratio: float
    min_length: int
    max_length: int


class BooleanColumnProfile(MainModel):
    true_token_count: int
    false_token_count: int
    unrecognized_count: int
    recognized_ratio: float


class IntegerColumnProfile(MainModel):
    parse_match_count: int
    parse_match_ratio: float


class DecimalColumnProfile(MainModel):
    parse_match_count: int
    parse_match_ratio: float
    swapped_match_count: int
    swapped_match_ratio: float
    separator_mismatch_detected: bool


class PercentageColumnProfile(MainModel):
    parse_match_count: int
    parse_match_ratio: float
    swapped_match_count: int
    swapped_match_ratio: float
    separator_mismatch_detected: bool


class SignedColumnProfile(MainModel):
    parse_match_count: int
    parse_match_ratio: float
    swapped_match_count: int
    swapped_match_ratio: float
    separator_mismatch_detected: bool


class CurrencyColumnProfile(MainModel):
    symbol_distribution: dict[str, int]
    dominant_symbol: str | None
    dominant_symbol_ratio: float
    has_mixed_symbols: bool
    parse_match_count: int
    parse_match_ratio: float
    swapped_match_count: int
    swapped_match_ratio: float
    separator_mismatch_detected: bool


class AccountingColumnProfile(MainModel):
    symbol_distribution: dict[str, int]
    dominant_symbol: str | None
    dominant_symbol_ratio: float
    has_mixed_symbols: bool
    parse_match_count: int
    parse_match_ratio: float
    swapped_match_count: int
    swapped_match_ratio: float
    separator_mismatch_detected: bool


class DateColumnProfile(MainModel):
    format_match_count: int
    format_match_ratio: float


ColumnProfile = (
    StringColumnProfile
    | BooleanColumnProfile
    | IntegerColumnProfile
    | DecimalColumnProfile
    | PercentageColumnProfile
    | SignedColumnProfile
    | CurrencyColumnProfile
    | AccountingColumnProfile
    | DateColumnProfile
)


class ColumnProfileStats(MainModel):
    label: str
    column_type: ColumnType
    counts: ColumnCounts
    null_ratio: float
    nullish_ratio: float
    type_profile: ColumnProfile


class ProfilingOutput(MainModel):
    source_checksum: str
    row_count: int
    empty_row_count: int
    column_count: int
    pattern_consistency_ratio: float
    completeness_ratio: float
    column_stats: dict[str, ColumnProfileStats]
    issues: list[NormalizationIssue]
