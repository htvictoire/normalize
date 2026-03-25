"""Column config base classes and shared type aliases."""

from __future__ import annotations

from typing import Literal

from shared.models.base import MainModel

ColumnType = Literal[
    "string", "boolean", "integer", "decimal", "currency",
    "percentage", "signed", "accounting", "date",
]
GroupingStyle = Literal["western", "indian"]


class NumericColumnConfig(MainModel):
    """Base for all numeric config types: carries thousand separator and grouping style."""

    thousand_separator: str
    grouping_style: GroupingStyle


class DecimalFamilyColumnConfig(NumericColumnConfig):
    """Base for decimal-family config types: adds decimal separator fields."""

    decimal_separator: str
    allow_leading_decimal_point: bool


class SignedFamilyColumnConfig(DecimalFamilyColumnConfig):
    """Base for sign-aware config types: adds sign marker fields."""

    positive_markers: tuple[str, ...]
    negative_markers: tuple[str, ...]
    parentheses_as_negative: bool
