"""Concrete column profile types and the ColumnProfile discriminated union."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from shared.models.base import MainModel
from shared.models.profiling.base import (
    ParseMatchProfile,
    SeparatorMismatchProfile,
    SymbolDistributionProfile,
)


class StringColumnProfile(MainModel):
    profile_type: Literal["string"] = "string"
    distinct_count: int
    distinct_ratio: float
    min_length: int
    max_length: int


class BooleanColumnProfile(MainModel):
    profile_type: Literal["boolean"] = "boolean"
    true_token_count: int
    false_token_count: int
    unrecognized_count: int
    recognized_ratio: float


class IntegerColumnProfile(ParseMatchProfile):
    profile_type: Literal["integer"] = "integer"


class DecimalColumnProfile(SeparatorMismatchProfile):
    profile_type: Literal["decimal"] = "decimal"


class PercentageColumnProfile(SeparatorMismatchProfile):
    profile_type: Literal["percentage"] = "percentage"


class SignedColumnProfile(SeparatorMismatchProfile):
    profile_type: Literal["signed"] = "signed"


class CurrencyColumnProfile(SymbolDistributionProfile, SeparatorMismatchProfile):
    profile_type: Literal["currency"] = "currency"


class AccountingColumnProfile(SymbolDistributionProfile, SeparatorMismatchProfile):
    profile_type: Literal["accounting"] = "accounting"


class DateColumnProfile(MainModel):
    profile_type: Literal["date"] = "date"
    format_match_count: int
    format_match_ratio: float


ColumnProfile = Annotated[
    (
        StringColumnProfile
        | BooleanColumnProfile
        | IntegerColumnProfile
        | DecimalColumnProfile
        | PercentageColumnProfile
        | SignedColumnProfile
        | CurrencyColumnProfile
        | AccountingColumnProfile
        | DateColumnProfile
    ),
    Field(discriminator="profile_type"),
]
