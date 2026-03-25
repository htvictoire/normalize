"""Concrete column configuration types and the ColumnConfig discriminated union."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, Literal, cast

from pydantic import Field, TypeAdapter

from shared.models.base import MainModel
from shared.models.column.base import (
    ColumnType,
    DecimalFamilyColumnConfig,
    NumericColumnConfig,
    SignedFamilyColumnConfig,
)


class StringColumnConfig(MainModel):
    """Declared string column configuration."""

    type: Literal["string"] = "string"


class BooleanColumnConfig(MainModel):
    """Declared boolean column configuration."""

    true_tokens: tuple[str, ...]
    false_tokens: tuple[str, ...]
    type: Literal["boolean"] = "boolean"


class IntegerColumnConfig(NumericColumnConfig):
    """Declared integer column configuration."""

    type: Literal["integer"] = "integer"


class DecimalColumnConfig(DecimalFamilyColumnConfig):
    """Declared decimal column configuration."""

    type: Literal["decimal"] = "decimal"


class CurrencyColumnConfig(DecimalFamilyColumnConfig):
    """Declared currency column configuration."""

    type: Literal["currency"] = "currency"


class PercentageColumnConfig(DecimalFamilyColumnConfig):
    """Declared percentage column configuration."""

    type: Literal["percentage"] = "percentage"


class SignedColumnConfig(SignedFamilyColumnConfig):
    """Declared signed column configuration — numeric values where sign is encoded via markers."""

    type: Literal["signed"] = "signed"


class AccountingColumnConfig(SignedFamilyColumnConfig):
    """Declared accounting column — currency symbols present alongside sign markers."""

    type: Literal["accounting"] = "accounting"


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
        | PercentageColumnConfig
        | SignedColumnConfig
        | AccountingColumnConfig
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
