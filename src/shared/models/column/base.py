"""Column config capability bases and shared scalar type aliases."""

from __future__ import annotations

from typing import Literal

from shared.models.base import MainModel

ColumnType = Literal[
    "string", "identifier", "boolean", "integer", "decimal", "currency",
    "percentage", "signed", "accounting", "date", "datetime", "time",
    "country_code", "currency_code", "language_code",
    "categorical", "email", "url", "ip_address", "phone",
]


class NumericFormattingColumnConfig(MainModel):
    """Capability base for numeric configs.

    Carries no separator or grouping settings: a column cannot declare a locale,
    because one column routinely holds several. The decimal separator is resolved
    per value in ``shared.parsing.numeric``, which handles western, european,
    indian and apostrophe/space grouping alike.
    """


class DecimalSyntaxColumnConfig(NumericFormattingColumnConfig):
    """Capability base for configs that admit a fractional part."""


class SignedNotationColumnConfig(DecimalSyntaxColumnConfig):
    """Capability base for configs with explicit sign marker notation."""

    positive_markers: tuple[str, ...]
    negative_markers: tuple[str, ...]
    parentheses_as_negative: bool
