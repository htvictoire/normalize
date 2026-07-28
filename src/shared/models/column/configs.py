"""Concrete column configuration types and the ColumnConfig discriminated union."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, Literal, cast

from pydantic import Field, TypeAdapter

from shared.models.base import MainModel
from shared.models.column.base import (
    ColumnType,
    DecimalSyntaxColumnConfig,
    NumericFormattingColumnConfig,
    SignedNotationColumnConfig,
)


class StringColumnConfig(MainModel):
    """Declared string column configuration."""

    type: Literal["string"] = "string"


class IdentifierColumnConfig(MainModel):
    """Declared identifier column; values are preserved as strings."""

    identifier_kind: Literal["primary", "foreign", "business_key", "opaque"] = "opaque"
    type: Literal["identifier"] = "identifier"


class BooleanColumnConfig(MainModel):
    """Declared boolean column configuration.

    Tokens are not per-column; parsing uses the canonical set in
    ``shared.parsing.boolean``.
    """

    type: Literal["boolean"] = "boolean"


class IntegerColumnConfig(NumericFormattingColumnConfig):
    """Declared integer column configuration."""

    type: Literal["integer"] = "integer"


class DecimalColumnConfig(DecimalSyntaxColumnConfig):
    """Declared decimal column configuration."""

    type: Literal["decimal"] = "decimal"


class CurrencyColumnConfig(DecimalSyntaxColumnConfig):
    """Declared currency column configuration."""

    type: Literal["currency"] = "currency"


class PercentageColumnConfig(DecimalSyntaxColumnConfig):
    """Declared percentage column configuration."""

    type: Literal["percentage"] = "percentage"


class SignedColumnConfig(SignedNotationColumnConfig):
    """Declared signed column configuration — numeric values where sign is encoded via markers."""

    type: Literal["signed"] = "signed"


class AccountingColumnConfig(SignedNotationColumnConfig):
    """Declared accounting column — currency symbols present alongside sign markers."""

    type: Literal["accounting"] = "accounting"


class DateColumnConfig(MainModel):
    """Declared date column configuration.

    Formats are not per-column; parsing uses the canonical chain in
    ``shared.parsing.temporal``.
    """

    day_first: bool = Field(
        description=(
            "Whether numeric day/month values read day-first: true parses "
            "01/02/2023 as 1 February, false as January 2. Decide from "
            "unambiguous values (a first field greater than 12 proves "
            "day-first); if every value is ambiguous, choose from the column's "
            "locale context and reflect the uncertainty in the confidence. A "
            "column of spreadsheet serial-number dates (integers near 45000, "
            "often labelled serial/posting/period) is a date column, not an "
            "integer column; the engine converts serials to dates (use false)."
        )
    )
    type: Literal["date"] = "date"


class DateTimeColumnConfig(MainModel):
    """Declared datetime/timestamp column configuration.

    Formats are not per-column; parsing uses the canonical chain in
    ``shared.parsing.temporal``.
    """

    day_first: bool = Field(
        description=(
            "Whether numeric day/month values read day-first: true parses "
            "01/02/2023 04:05 as 1 February, false as January 2. Decide from "
            "unambiguous values (a first field greater than 12 proves "
            "day-first); if every value is ambiguous, choose from the column's "
            "locale context and reflect the uncertainty in the confidence."
        )
    )
    type: Literal["datetime"] = "datetime"


class TimeColumnConfig(MainModel):
    """Declared time-of-day column configuration.

    Formats are not per-column; parsing uses the canonical chain in
    ``shared.parsing.temporal``.
    """

    type: Literal["time"] = "time"


class CountryCodeColumnConfig(MainModel):
    """Declared ISO 3166-1 country-code column configuration."""

    code_format: Literal["alpha_2", "alpha_3"]
    type: Literal["country_code"] = "country_code"


class CurrencyCodeColumnConfig(MainModel):
    """Declared ISO 4217 alpha-3 currency-code column configuration."""

    type: Literal["currency_code"] = "currency_code"


class LanguageCodeColumnConfig(MainModel):
    """Declared ISO 639 language-code column configuration."""

    code_format: Literal["alpha_2", "alpha_3"]
    type: Literal["language_code"] = "language_code"


class CategoricalColumnConfig(MainModel):
    """AI-only declared categorical column.

    Matching is case-insensitive and whitespace-trimmed: a source value that
    equals a canonical value once both are trimmed and lowercased is normalized
    to that canonical spelling. Anything else is kept as-is and flagged.
    """

    canonical_values: tuple[str, ...] = Field(
        description=(
            "The distinct categories this column can hold, each written once in its "
            "canonical form. List each category a single time; do not include case "
            "or whitespace variants of the same category."
        )
    )
    type: Literal["categorical"] = "categorical"


class EmailColumnConfig(MainModel):
    """AI-only declared email-address column."""

    type: Literal["email"] = "email"


class UrlColumnConfig(MainModel):
    """AI-only declared URL column."""

    type: Literal["url"] = "url"


class IpAddressColumnConfig(MainModel):
    """AI-only declared IP-address column."""

    version: Literal["any", "v4", "v6"] = "any"
    type: Literal["ip_address"] = "ip_address"


class PhoneColumnConfig(MainModel):
    """AI-only declared phone-number column with deterministic E.164-like validation."""

    type: Literal["phone"] = "phone"


# Suggestion schema contract:
# - CoreColumnConfig is available in every suggestion mode.
# - RuleBasedExtendedColumnConfig is additionally available to rule-based and AI when
#   extended_type_detection=true.
# - AiOnlyColumnConfig is available only to AI when extended_type_detection=true.
# All variants remain executable after confirmation through ColumnConfig.
type CoreColumnConfigModel = (
    StringColumnConfig
    | IdentifierColumnConfig
    | BooleanColumnConfig
    | IntegerColumnConfig
    | DecimalColumnConfig
    | CurrencyColumnConfig
    | PercentageColumnConfig
    | SignedColumnConfig
    | AccountingColumnConfig
    | DateColumnConfig
    | DateTimeColumnConfig
    | TimeColumnConfig
)


type RuleBasedExtendedColumnConfigModel = (
    CountryCodeColumnConfig | CurrencyCodeColumnConfig | LanguageCodeColumnConfig
)


type AiOnlyColumnConfigModel = (
    CategoricalColumnConfig
    | EmailColumnConfig
    | UrlColumnConfig
    | IpAddressColumnConfig
    | PhoneColumnConfig
)


CoreColumnConfig = Annotated[CoreColumnConfigModel, Field(discriminator="type")]
RuleBasedExtendedColumnConfig = Annotated[
    RuleBasedExtendedColumnConfigModel,
    Field(discriminator="type"),
]
AiOnlyColumnConfig = Annotated[AiOnlyColumnConfigModel, Field(discriminator="type")]

type ColumnConfigModel = (
    CoreColumnConfigModel | RuleBasedExtendedColumnConfigModel | AiOnlyColumnConfigModel
)

ColumnConfig = Annotated[ColumnConfigModel, Field(discriminator="type")]

_COLUMN_CONFIG_ADAPTER: TypeAdapter[ColumnConfig] = TypeAdapter(ColumnConfig)


def column_config_type(config: ColumnConfig) -> ColumnType:
    """Return the discriminant type string for one column config."""
    return config.type


def column_config_to_dict(config: ColumnConfig) -> dict[str, Any]:
    """Serialize one strict column config model to a deterministic dict."""
    return cast(
        dict[str, Any],
        _COLUMN_CONFIG_ADAPTER.dump_python(config, mode="json"),
    )


def serialize_column_config_map(
    column_config: Mapping[str, ColumnConfig],
) -> dict[str, dict[str, Any]]:
    """Serialize position-keyed column config mapping."""
    return {
        position_key: column_config_to_dict(spec) for position_key, spec in column_config.items()
    }
