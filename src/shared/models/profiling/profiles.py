"""Concrete column profile types and the ColumnProfile union."""

from __future__ import annotations

from shared.models.base import MainModel
from shared.models.profiling.base import (
    ParseMatchProfile,
    SeparatorMismatchProfile,
    SymbolDistributionProfile,
)


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


class IntegerColumnProfile(ParseMatchProfile):
    pass


class DecimalColumnProfile(SeparatorMismatchProfile):
    pass


class PercentageColumnProfile(SeparatorMismatchProfile):
    pass


class SignedColumnProfile(SeparatorMismatchProfile):
    pass


class CurrencyColumnProfile(SymbolDistributionProfile, SeparatorMismatchProfile):
    pass


class AccountingColumnProfile(SymbolDistributionProfile, SeparatorMismatchProfile):
    pass


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
