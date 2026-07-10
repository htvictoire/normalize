"""Column config capability bases and shared scalar type aliases."""

from __future__ import annotations

from typing import Literal

from shared.models.base import MainModel

ColumnType = Literal[
    "string", "boolean", "integer", "decimal", "currency",
    "percentage", "signed", "accounting", "date", "datetime", "time",
]
GroupingStyle = Literal["western", "indian"]


class NumericFormattingColumnConfig(MainModel):
    """Capability base for configs with numeric grouping/formatting settings."""

    thousand_separator: str
    grouping_style: GroupingStyle


class DecimalSyntaxColumnConfig(NumericFormattingColumnConfig):
    """Capability base for configs with decimal separator syntax settings."""

    decimal_separator: str
    allow_leading_decimal_point: bool


class SignedNotationColumnConfig(DecimalSyntaxColumnConfig):
    """Capability base for configs with explicit sign marker notation."""

    positive_markers: tuple[str, ...]
    negative_markers: tuple[str, ...]
    parentheses_as_negative: bool
