"""Per-column configuration types shared across app and engine layers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, Literal, cast

from pydantic import Field, TypeAdapter

from shared.models.base import MainModel

ColumnType = Literal["string", "boolean", "integer", "decimal", "currency", "date"]
GroupingStyle = Literal["western", "indian"]


class StringColumnConfig(MainModel):
    """Declared string column configuration."""

    type: Literal["string"] = "string"


class BooleanColumnConfig(MainModel):
    """Declared boolean column configuration."""

    type: Literal["boolean"] = "boolean"


class IntegerColumnConfig(MainModel):
    """Declared integer column configuration."""

    thousand_separator: str
    grouping_style: GroupingStyle
    type: Literal["integer"] = "integer"


class DecimalColumnConfig(MainModel):
    """Declared decimal column configuration."""

    decimal_separator: str
    thousand_separator: str
    grouping_style: GroupingStyle
    allow_leading_decimal_point: bool
    type: Literal["decimal"] = "decimal"


class CurrencyColumnConfig(MainModel):
    """Declared currency column configuration."""

    decimal_separator: str
    thousand_separator: str
    grouping_style: GroupingStyle
    allow_leading_decimal_point: bool
    type: Literal["currency"] = "currency"


class DateColumnConfig(MainModel):
    """Declared date column configuration."""

    date_format: str
    type: Literal["date"] = "date"


ColumnConfig = Annotated[
    (
        StringColumnConfig
        | BooleanColumnConfig
        | IntegerColumnConfig
        | DecimalColumnConfig
        | CurrencyColumnConfig
        | DateColumnConfig
    ),
    Field(discriminator="type"),
]

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
