"""Concrete column configuration types and the ColumnConfig discriminated union."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, Literal, cast

from pydantic import Field, TypeAdapter, field_validator, model_validator

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


class BooleanColumnConfig(MainModel):
    """Declared boolean column configuration."""

    true_tokens: tuple[str, ...]
    false_tokens: tuple[str, ...]
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
    """Declared date column configuration."""

    date_format: str = Field(
        description=(
            "A DuckDB strptime format (e.g. %Y-%m-%d, %d/%m/%Y, %d %b %Y), or the "
            "literal EXCEL_SERIAL for spreadsheet serial-number dates. The engine "
            "parses dates with TRY_STRPTIME, so the format must be one it can "
            "execute. If the column's dates cannot be expressed as such a format "
            "(e.g. localized month names or ordinal suffixes), classify the column "
            "as string instead of date."
        )
    )
    type: Literal["date"] = "date"

    @field_validator("date_format")
    @classmethod
    def _require_strptime_or_sentinel(cls, value: str) -> str:
        """Reject formats the engine cannot execute (e.g. human notation 'yyyy-mm-dd')."""
        if value != "EXCEL_SERIAL" and "%" not in value:
            raise ValueError(
                f"date_format must be a strptime pattern containing '%' "
                f"or the literal 'EXCEL_SERIAL', got {value!r}"
            )
        return value


class DateTimeColumnConfig(MainModel):
    """Declared datetime/timestamp column configuration."""

    datetime_format: str = Field(
        description=(
            "A DuckDB strptime format (e.g. %Y-%m-%d %H:%M:%S, %d/%m/%Y %H:%M), "
            "or the literal EXCEL_SERIAL for spreadsheet serial-number timestamps. "
            "The engine parses datetimes with TRY_STRPTIME, so the format must be "
            "one it can execute. If the column's datetimes cannot be expressed as "
            "such a format, classify the column as string instead of datetime."
        )
    )
    type: Literal["datetime"] = "datetime"

    @field_validator("datetime_format")
    @classmethod
    def _require_strptime_or_sentinel(cls, value: str) -> str:
        """Reject formats the engine cannot execute (e.g. human notation)."""
        if value != "EXCEL_SERIAL" and "%" not in value:
            raise ValueError(
                f"datetime_format must be a strptime pattern containing '%' "
                f"or the literal 'EXCEL_SERIAL', got {value!r}"
            )
        return value


class TimeColumnConfig(MainModel):
    """Declared time-of-day column configuration."""

    time_format: str = Field(
        description=(
            "A DuckDB strptime format for time-of-day values (e.g. %H:%M:%S, "
            "%H:%M, %I:%M %p). The engine parses times with TRY_STRPTIME, so "
            "the format must be one it can execute. If the column's times cannot "
            "be expressed as such a format, classify the column as string instead "
            "of time."
        )
    )
    type: Literal["time"] = "time"

    @field_validator("time_format")
    @classmethod
    def _require_strptime_pattern(cls, value: str) -> str:
        """Reject formats the engine cannot execute (e.g. human notation)."""
        if "%" not in value:
            raise ValueError(
                f"time_format must be a strptime pattern containing '%', got {value!r}"
            )
        return value


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
    """AI-only declared categorical column with explicit confirmed value mapping."""

    canonical_values: tuple[str, ...]
    value_map: dict[str, str]
    unknown_value_policy: Literal["issue_and_keep", "issue_and_null", "keep"]
    type: Literal["categorical"] = "categorical"

    @model_validator(mode="after")
    def _validate_mapping_targets(self) -> CategoricalColumnConfig:
        canonical = set(self.canonical_values)
        invalid_targets = sorted(
            {target for target in self.value_map.values() if target not in canonical}
        )
        if invalid_targets:
            raise ValueError(
                f"value_map targets must be canonical_values, got {invalid_targets!r}"
            )
        return self


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
    CountryCodeColumnConfig
    | CurrencyCodeColumnConfig
    | LanguageCodeColumnConfig
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
    CoreColumnConfigModel
    | RuleBasedExtendedColumnConfigModel
    | AiOnlyColumnConfigModel
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
        position_key: column_config_to_dict(spec)
        for position_key, spec in column_config.items()
    }
