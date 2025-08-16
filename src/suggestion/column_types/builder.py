"""Build suggested column configuration models from inference output."""

from __future__ import annotations

from collections.abc import Mapping

from shared.models.column import (
    BooleanColumnConfig,
    ColumnConfig,
    CurrencyColumnConfig,
    DateColumnConfig,
    DecimalColumnConfig,
    IntegerColumnConfig,
    StringColumnConfig,
)
from suggestion.column_types.models import NumericSuggestion


def build_suggested_column_config(
    *,
    inferred_types: Mapping[str, str],
    inferred_date_formats: Mapping[str, str],
    inferred_numeric_suggestions: Mapping[str, NumericSuggestion],
    position_to_name: Mapping[str, str],
) -> dict[str, ColumnConfig]:
    """Map inferred canonical column signals into position-keyed config."""
    config: dict[str, ColumnConfig] = {}
    for position_key, column_name in position_to_name.items():
        inferred_type = inferred_types[column_name]
        date_format = inferred_date_formats.get(column_name)
        numeric = inferred_numeric_suggestions.get(column_name)
        config[position_key] = column_config_for_inferred_type(
            inferred_type,
            date_format=date_format,
            numeric=numeric,
        )
    return config


def column_config_for_inferred_type(
    inferred_type: str,
    *,
    date_format: str | None,
    numeric: NumericSuggestion | None,
) -> ColumnConfig:
    """Build one ColumnConfig from inferred type and optional format hints."""
    if inferred_type == "boolean":
        return BooleanColumnConfig()
    if inferred_type == "integer":
        if numeric is None:
            raise ValueError("integer inference requires numeric format inference")
        return IntegerColumnConfig(
            thousand_separator=numeric.thousand_separator,
            grouping_style=numeric.grouping_style,
        )
    if inferred_type == "decimal":
        if numeric is None:
            raise ValueError("decimal inference requires numeric format inference")
        return DecimalColumnConfig(
            decimal_separator=numeric.decimal_separator,
            thousand_separator=numeric.thousand_separator,
            grouping_style=numeric.grouping_style,
            allow_leading_decimal_point=numeric.allow_leading_decimal_point,
        )
    if inferred_type == "currency":
        if numeric is None:
            raise ValueError("currency inference requires numeric format inference")
        return CurrencyColumnConfig(
            decimal_separator=numeric.decimal_separator,
            thousand_separator=numeric.thousand_separator,
            grouping_style=numeric.grouping_style,
            allow_leading_decimal_point=numeric.allow_leading_decimal_point,
        )
    if inferred_type == "date":
        if date_format is None:
            raise ValueError("date inference requires an inferred date_format")
        return DateColumnConfig(date_format=date_format)
    return StringColumnConfig()
