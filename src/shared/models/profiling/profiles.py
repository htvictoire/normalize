"""Concrete column profile types and the ColumnProfile discriminated union."""

from __future__ import annotations

from typing import Annotated, Literal, overload

from pydantic import Field

from shared.models.base import MainModel
from shared.models.column import (
    AccountingColumnConfig,
    BooleanColumnConfig,
    CategoricalColumnConfig,
    ColumnConfig,
    CountryCodeColumnConfig,
    CurrencyCodeColumnConfig,
    CurrencyColumnConfig,
    DateColumnConfig,
    DateTimeColumnConfig,
    DecimalColumnConfig,
    EmailColumnConfig,
    IntegerColumnConfig,
    IpAddressColumnConfig,
    LanguageCodeColumnConfig,
    PercentageColumnConfig,
    PhoneColumnConfig,
    SignedColumnConfig,
    StringColumnConfig,
    TimeColumnConfig,
    UrlColumnConfig,
)
from shared.models.profiling.base import (
    AccountingSignProfile,
    CurrencyFormatProfile,
    DecimalStatsProfile,
    MonetaryProfile,
    ParseMatchProfile,
    ValidityProfile,
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


class CountryCodeColumnProfile(ValidityProfile):
    profile_type: Literal["country_code"] = "country_code"


class CurrencyCodeColumnProfile(ValidityProfile):
    profile_type: Literal["currency_code"] = "currency_code"


class LanguageCodeColumnProfile(ValidityProfile):
    profile_type: Literal["language_code"] = "language_code"


class DateTimeColumnProfile(MainModel):
    profile_type: Literal["datetime"] = "datetime"
    format_match_count: int
    format_match_ratio: float


class TimeColumnProfile(MainModel):
    profile_type: Literal["time"] = "time"
    format_match_count: int
    format_match_ratio: float


class CategoricalColumnProfile(ValidityProfile):
    profile_type: Literal["categorical"] = "categorical"


class EmailColumnProfile(ValidityProfile):
    profile_type: Literal["email"] = "email"


class UrlColumnProfile(ValidityProfile):
    profile_type: Literal["url"] = "url"


class IpAddressColumnProfile(ValidityProfile):
    profile_type: Literal["ip_address"] = "ip_address"


class PhoneColumnProfile(ValidityProfile):
    profile_type: Literal["phone"] = "phone"


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
    | type[CountryCodeColumnProfile]
    | type[CurrencyCodeColumnProfile]
    | type[LanguageCodeColumnProfile]
    | type[DateTimeColumnProfile]
    | type[TimeColumnProfile]
    | type[CategoricalColumnProfile]
    | type[EmailColumnProfile]
    | type[UrlColumnProfile]
    | type[IpAddressColumnProfile]
    | type[PhoneColumnProfile]
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
    CountryCodeColumnConfig: CountryCodeColumnProfile,
    CurrencyCodeColumnConfig: CurrencyCodeColumnProfile,
    LanguageCodeColumnConfig: LanguageCodeColumnProfile,
    DateTimeColumnConfig: DateTimeColumnProfile,
    TimeColumnConfig: TimeColumnProfile,
    CategoricalColumnConfig: CategoricalColumnProfile,
    EmailColumnConfig: EmailColumnProfile,
    UrlColumnConfig: UrlColumnProfile,
    IpAddressColumnConfig: IpAddressColumnProfile,
    PhoneColumnConfig: PhoneColumnProfile,
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


@overload
def profile_class_for_config(config: CountryCodeColumnConfig) -> type[CountryCodeColumnProfile]: ...


@overload
def profile_class_for_config(
    config: CurrencyCodeColumnConfig,
) -> type[CurrencyCodeColumnProfile]: ...


@overload
def profile_class_for_config(
    config: LanguageCodeColumnConfig,
) -> type[LanguageCodeColumnProfile]: ...


@overload
def profile_class_for_config(config: DateTimeColumnConfig) -> type[DateTimeColumnProfile]: ...


@overload
def profile_class_for_config(config: TimeColumnConfig) -> type[TimeColumnProfile]: ...


@overload
def profile_class_for_config(
    config: CategoricalColumnConfig,
) -> type[CategoricalColumnProfile]: ...


@overload
def profile_class_for_config(config: EmailColumnConfig) -> type[EmailColumnProfile]: ...


@overload
def profile_class_for_config(config: UrlColumnConfig) -> type[UrlColumnProfile]: ...


@overload
def profile_class_for_config(config: IpAddressColumnConfig) -> type[IpAddressColumnProfile]: ...


@overload
def profile_class_for_config(config: PhoneColumnConfig) -> type[PhoneColumnProfile]: ...


def profile_class_for_config(config: ColumnConfig) -> ColumnProfileClass:
    """Return the concrete profiling model class for one declared column config."""
    return _PROFILE_CLASS_BY_CONFIG[type(config)]


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
        | CountryCodeColumnProfile
        | CurrencyCodeColumnProfile
        | LanguageCodeColumnProfile
        | DateTimeColumnProfile
        | TimeColumnProfile
        | CategoricalColumnProfile
        | EmailColumnProfile
        | UrlColumnProfile
        | IpAddressColumnProfile
        | PhoneColumnProfile
    ),
    Field(discriminator="profile_type"),
]
