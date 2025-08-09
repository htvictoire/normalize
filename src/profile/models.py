"""Profile phase output models."""

from __future__ import annotations

from shared.models.base import MainModel
from shared.models.column import ColumnType
from shared.models.issues import NormalizationIssue


class CurrencyColumnProfile(MainModel):
    symbol_distribution: dict[str, int]
    dominant_symbol: str | None
    dominant_symbol_ratio: float
    non_nullish_count: int
    has_mixed_symbols: bool


class NumericColumnProfile(MainModel):
    parse_match_count: int
    non_nullish_count: int
    parse_match_ratio: float
    swapped_match_count: int
    swapped_match_ratio: float
    separator_mismatch_detected: bool


class DateColumnProfile(MainModel):
    format_match_count: int
    non_nullish_count: int
    format_match_ratio: float


class BooleanColumnProfile(MainModel):
    true_token_count: int
    false_token_count: int
    unrecognized_count: int
    non_nullish_count: int
    recognized_ratio: float


class ColumnProfileStats(MainModel):
    column_type: ColumnType
    null_count: int
    non_null_count: int
    null_ratio: float
    type_profile: (
        CurrencyColumnProfile
        | NumericColumnProfile
        | DateColumnProfile
        | BooleanColumnProfile
        | None
    )


class ProfileOutput(MainModel):
    source_checksum: str
    row_count: int
    empty_row_count: int
    column_count: int
    pattern_consistency_ratio: float
    completeness_ratio: float
    column_stats: dict[str, ColumnProfileStats]
    issues: list[NormalizationIssue]
