"""Concrete column profile types and the ColumnProfile discriminated union."""

from __future__ import annotations

from typing import Annotated, Literal, cast, overload

from pydantic import Field

from shared.models.base import MainModel
from shared.models.column import (
    AccountingColumnConfig,
    BooleanColumnConfig,
    ColumnConfig,
    CurrencyColumnConfig,
    DateColumnConfig,
    DecimalColumnConfig,
    IntegerColumnConfig,
    PercentageColumnConfig,
    SignedColumnConfig,
    StringColumnConfig,
)
from shared.models.profiling.base import (
    AccountingSignProfile,
    CurrencyFormatProfile,
    DecimalStatsProfile,
    MonetaryProfile,
    ParseMatchProfile,
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


class DecimalColumnProfile(DecimalStatsProfile):
    profile_type: Literal["decimal"] = "decimal"


class PercentageColumnProfile(DecimalStatsProfile):
    profile_type: Literal["percentage"] = "percentage"


class SignedColumnProfile(DecimalStatsProfile):
    profile_type: Literal["signed"] = "signed"


class CurrencyColumnProfile(
    CurrencyFormatProfile,
    MonetaryProfile,
):
    profile_type: Literal["currency"] = "currency"


class AccountingColumnProfile(
    AccountingSignProfile,
    MonetaryProfile,
):
    profile_type: Literal["accounting"] = "accounting"


class DateColumnProfile(MainModel):
    profile_type: Literal["date"] = "date"
    format_match_count: int
    format_match_ratio: float


type ColumnProfileClass = (
    type[StringColumnProfile]
    | type[BooleanColumnProfile]
    | type[IntegerColumnProfile]
    | type[DecimalColumnProfile]
    | type[PercentageColumnProfile]
    | type[SignedColumnProfile]
    | type[CurrencyColumnProfile]
    | type[AccountingColumnProfile]
    | type[DateColumnProfile]
)

type DecimalLeafProfileClass = (
    type[DecimalColumnProfile]
    | type[PercentageColumnProfile]
    | type[SignedColumnProfile]
)

type DecimalStatsColumnConfig = (
    DecimalColumnConfig
    | PercentageColumnConfig
    | SignedColumnConfig
)

_PROFILE_CLASS_BY_CONFIG: dict[type[object], ColumnProfileClass] = {
    StringColumnConfig: StringColumnProfile,
    BooleanColumnConfig: BooleanColumnProfile,
    IntegerColumnConfig: IntegerColumnProfile,
    DecimalColumnConfig: DecimalColumnProfile,
    CurrencyColumnConfig: CurrencyColumnProfile,
    PercentageColumnConfig: PercentageColumnProfile,
    SignedColumnConfig: SignedColumnProfile,
    AccountingColumnConfig: AccountingColumnProfile,
    DateColumnConfig: DateColumnProfile,
}


@overload
def profile_class_for_config(config: StringColumnConfig) -> type[StringColumnProfile]: ...


@overload
def profile_class_for_config(config: BooleanColumnConfig) -> type[BooleanColumnProfile]: ...


@overload
def profile_class_for_config(config: IntegerColumnConfig) -> type[IntegerColumnProfile]: ...


@overload
def profile_class_for_config(config: DecimalColumnConfig) -> type[DecimalColumnProfile]: ...


@overload
def profile_class_for_config(config: CurrencyColumnConfig) -> type[CurrencyColumnProfile]: ...


@overload
def profile_class_for_config(config: PercentageColumnConfig) -> type[PercentageColumnProfile]: ...


@overload
def profile_class_for_config(config: SignedColumnConfig) -> type[SignedColumnProfile]: ...


@overload
def profile_class_for_config(config: AccountingColumnConfig) -> type[AccountingColumnProfile]: ...


@overload
def profile_class_for_config(config: DateColumnConfig) -> type[DateColumnProfile]: ...


def profile_class_for_config(config: ColumnConfig) -> ColumnProfileClass:
    """Return the concrete profiling model class for one declared column config."""
    return _PROFILE_CLASS_BY_CONFIG[type(config)]


def decimal_stats_profile_class_for_config(
    config: DecimalStatsColumnConfig,
) -> DecimalLeafProfileClass:
    """Return the decimal-style profile class for decimal/percentage/signed configs."""
    profile_cls = _PROFILE_CLASS_BY_CONFIG[type(config)]
    return cast("DecimalLeafProfileClass", profile_cls)


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
