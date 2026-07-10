"""Shared column type specs and capability helpers.

This module is the single source of truth for cross-cutting column semantics.
Concrete config models remain the declared type truth. Capability bases in
``base.py`` describe shared fields. The specs below connect each concrete type
to the capabilities that suggestion, conversion, and profiling can rely on.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeGuard

from shared.models.column.base import (
    ColumnType,
    DecimalSyntaxColumnConfig,
    SignedNotationColumnConfig,
)
from shared.models.column.configs import (
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
    IdentifierColumnConfig,
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

type ColumnCapability = Literal[
    "numeric_formatting",
    "decimal_syntax",
    "signed_notation",
    "monetary_symbol",
    "boolean_tokens",
    "identifier",
    "date_format",
    "datetime_format",
    "time_format",
    "standard_code",
    "ai_only",
    "categorical_mapping",
    "structured_string",
]

type ColumnConfigClass = (
    type[StringColumnConfig]
    | type[IdentifierColumnConfig]
    | type[BooleanColumnConfig]
    | type[IntegerColumnConfig]
    | type[DecimalColumnConfig]
    | type[CurrencyColumnConfig]
    | type[PercentageColumnConfig]
    | type[SignedColumnConfig]
    | type[AccountingColumnConfig]
    | type[DateColumnConfig]
    | type[DateTimeColumnConfig]
    | type[TimeColumnConfig]
    | type[CountryCodeColumnConfig]
    | type[CurrencyCodeColumnConfig]
    | type[LanguageCodeColumnConfig]
    | type[CategoricalColumnConfig]
    | type[EmailColumnConfig]
    | type[UrlColumnConfig]
    | type[IpAddressColumnConfig]
    | type[PhoneColumnConfig]
)


@dataclass(frozen=True)
class ColumnTypeSpec:
    """Shared semantic contract for one declared column type."""

    type: ColumnType
    config_cls: ColumnConfigClass
    capabilities: frozenset[ColumnCapability]


COLUMN_TYPE_SPECS: tuple[ColumnTypeSpec, ...] = (
    ColumnTypeSpec("string", StringColumnConfig, frozenset()),
    ColumnTypeSpec("identifier", IdentifierColumnConfig, frozenset({"identifier"})),
    ColumnTypeSpec("boolean", BooleanColumnConfig, frozenset({"boolean_tokens"})),
    ColumnTypeSpec("integer", IntegerColumnConfig, frozenset({"numeric_formatting"})),
    ColumnTypeSpec(
        "decimal",
        DecimalColumnConfig,
        frozenset({"numeric_formatting", "decimal_syntax"}),
    ),
    ColumnTypeSpec(
        "currency",
        CurrencyColumnConfig,
        frozenset({"numeric_formatting", "decimal_syntax", "monetary_symbol"}),
    ),
    ColumnTypeSpec(
        "percentage",
        PercentageColumnConfig,
        frozenset({"numeric_formatting", "decimal_syntax"}),
    ),
    ColumnTypeSpec(
        "signed",
        SignedColumnConfig,
        frozenset({"numeric_formatting", "decimal_syntax", "signed_notation"}),
    ),
    ColumnTypeSpec(
        "accounting",
        AccountingColumnConfig,
        frozenset(
            {
                "numeric_formatting",
                "decimal_syntax",
                "signed_notation",
                "monetary_symbol",
            }
        ),
    ),
    ColumnTypeSpec("date", DateColumnConfig, frozenset({"date_format"})),
    ColumnTypeSpec("datetime", DateTimeColumnConfig, frozenset({"datetime_format"})),
    ColumnTypeSpec("time", TimeColumnConfig, frozenset({"time_format"})),
    ColumnTypeSpec("country_code", CountryCodeColumnConfig, frozenset({"standard_code"})),
    ColumnTypeSpec("currency_code", CurrencyCodeColumnConfig, frozenset({"standard_code"})),
    ColumnTypeSpec("language_code", LanguageCodeColumnConfig, frozenset({"standard_code"})),
    ColumnTypeSpec(
        "categorical",
        CategoricalColumnConfig,
        frozenset({"ai_only", "categorical_mapping"}),
    ),
    ColumnTypeSpec("email", EmailColumnConfig, frozenset({"ai_only", "structured_string"})),
    ColumnTypeSpec("url", UrlColumnConfig, frozenset({"ai_only", "structured_string"})),
    ColumnTypeSpec(
        "ip_address",
        IpAddressColumnConfig,
        frozenset({"ai_only", "structured_string"}),
    ),
    ColumnTypeSpec("phone", PhoneColumnConfig, frozenset({"ai_only", "structured_string"})),
)

_TYPE_SPEC_BY_TYPE: dict[ColumnType, ColumnTypeSpec] = {
    spec.type: spec for spec in COLUMN_TYPE_SPECS
}
_TYPE_SPEC_BY_CONFIG_CLASS: dict[ColumnConfigClass, ColumnTypeSpec] = {
    spec.config_cls: spec for spec in COLUMN_TYPE_SPECS
}


def column_type_spec(column_type: ColumnType) -> ColumnTypeSpec:
    """Return the shared semantic spec for one declared type string."""
    return _TYPE_SPEC_BY_TYPE[column_type]


def spec_for_config(config: ColumnConfig) -> ColumnTypeSpec:
    """Return the shared semantic spec for one concrete config instance."""
    return _TYPE_SPEC_BY_CONFIG_CLASS[type(config)]


def column_capabilities(config: ColumnConfig) -> frozenset[ColumnCapability]:
    """Return the declared capability set for one concrete config instance."""
    return spec_for_config(config).capabilities


def config_has_capability(config: ColumnConfig, capability: ColumnCapability) -> bool:
    """Return whether one config advertises a given shared capability."""
    return capability in column_capabilities(config)


def has_decimal_syntax(config: ColumnConfig) -> TypeGuard[DecimalSyntaxColumnConfig]:
    """Type guard for configs with decimal separator syntax fields."""
    return config_has_capability(config, "decimal_syntax")


def has_signed_notation(config: ColumnConfig) -> TypeGuard[SignedNotationColumnConfig]:
    """Type guard for configs with explicit sign marker notation."""
    return config_has_capability(config, "signed_notation")


def has_monetary_symbol(
    config: ColumnConfig,
) -> TypeGuard[CurrencyColumnConfig | AccountingColumnConfig]:
    """Type guard for configs whose values include monetary symbol tokens."""
    return config_has_capability(config, "monetary_symbol")
