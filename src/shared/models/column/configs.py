"""Concrete column configuration types and the ColumnConfig discriminated union."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, Literal, cast

from pydantic import Field, TypeAdapter, field_validator

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
