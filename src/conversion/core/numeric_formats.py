"""Numeric format config helpers (separator + grouping style)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from shared.utils.column import normalize_position_key

GROUPING_STYLE_WESTERN: Final[str] = "western"
GROUPING_STYLE_INDIAN: Final[str] = "indian"
ALLOWED_GROUPING_STYLES: Final[frozenset[str]] = frozenset(
    {GROUPING_STYLE_WESTERN, GROUPING_STYLE_INDIAN}
)


@dataclass(frozen=True)
class NumericFormat:
    """Per-column numeric/currency parsing format."""

    decimal_separator: str
    thousand_separator: str
    grouping_style: str


def validate_grouping_style(grouping_style: str, *, field_name: str) -> str:
    """Normalize and validate one grouping style value."""
    normalized = grouping_style.strip().lower()
    if normalized not in ALLOWED_GROUPING_STYLES:
        allowed = ", ".join(sorted(ALLOWED_GROUPING_STYLES))
        raise ValueError(f"{field_name} must be one of: {allowed}")
    return normalized


def validate_separator_pair(
    decimal_separator: str,
    thousand_separator: str,
    *,
    field_prefix: str,
) -> None:
    """Validate decimal/thousand separator contract."""
    decimal_field = (
        "decimal_separator" if not field_prefix else f"{field_prefix}.decimal_separator"
    )
    thousand_field = (
        "thousand_separator" if not field_prefix else f"{field_prefix}.thousand_separator"
    )
    if len(decimal_separator) != 1:
        raise ValueError(f"{decimal_field} must be exactly one character")
    if thousand_separator and len(thousand_separator) != 1:
        raise ValueError(f"{thousand_field} must be empty or exactly one character")
    if thousand_separator and decimal_separator == thousand_separator:
        raise ValueError(f"{decimal_field} and thousand_separator must differ")


def normalize_numeric_formats_config(
    numeric_formats: Mapping[str, Mapping[str, str] | NumericFormat],
) -> dict[str, NumericFormat]:
    """Normalize position-keyed numeric format config into strict dataclasses."""
    normalized: dict[str, NumericFormat] = {}
    expected_keys = {"decimal_separator", "thousand_separator", "grouping_style"}
    for raw_key, raw_value in numeric_formats.items():
        if not isinstance(raw_key, str):
            raise TypeError(f"numeric_formats key must be a string, got {type(raw_key).__name__}")
        position_key = normalize_position_key(raw_key)
        if isinstance(raw_value, NumericFormat):
            validate_separator_pair(
                raw_value.decimal_separator,
                raw_value.thousand_separator,
                field_prefix=f"numeric_formats[{raw_key!r}]",
            )
            normalized_grouping_style = validate_grouping_style(
                raw_value.grouping_style,
                field_name=f"numeric_formats[{raw_key!r}].grouping_style",
            )
            normalized[position_key] = NumericFormat(
                decimal_separator=raw_value.decimal_separator,
                thousand_separator=raw_value.thousand_separator,
                grouping_style=normalized_grouping_style,
            )
            continue
        if not isinstance(raw_value, Mapping):
            raise TypeError(
                f"numeric_formats[{raw_key!r}] must be a mapping with decimal/thousand/grouping"
            )
        missing = sorted(expected_keys - set(raw_value))
        if missing:
            missing_keys = ", ".join(missing)
            raise ValueError(f"numeric_formats[{raw_key!r}] missing required keys: {missing_keys}")
        unexpected = sorted(set(raw_value) - expected_keys)
        if unexpected:
            unexpected_keys = ", ".join(unexpected)
            raise ValueError(f"numeric_formats[{raw_key!r}] has unexpected keys: {unexpected_keys}")

        decimal_separator = raw_value["decimal_separator"]
        thousand_separator = raw_value["thousand_separator"]
        grouping_style = raw_value["grouping_style"]
        if not isinstance(decimal_separator, str):
            raise TypeError(f"numeric_formats[{raw_key!r}].decimal_separator must be a string")
        if not isinstance(thousand_separator, str):
            raise TypeError(f"numeric_formats[{raw_key!r}].thousand_separator must be a string")
        if not isinstance(grouping_style, str):
            raise TypeError(f"numeric_formats[{raw_key!r}].grouping_style must be a string")

        validate_separator_pair(
            decimal_separator,
            thousand_separator,
            field_prefix=f"numeric_formats[{raw_key!r}]",
        )
        normalized_grouping_style = validate_grouping_style(
            grouping_style,
            field_name=f"numeric_formats[{raw_key!r}].grouping_style",
        )
        normalized[position_key] = NumericFormat(
            decimal_separator=decimal_separator,
            thousand_separator=thousand_separator,
            grouping_style=normalized_grouping_style,
        )
    return normalized


def resolve_numeric_formats_by_canonical(
    *,
    numeric_formats: Mapping[str, NumericFormat] | None,
    position_to_canonical: Mapping[str, str],
) -> dict[str, NumericFormat]:
    """Resolve position-key numeric formats to canonical column names."""
    resolved: dict[str, NumericFormat] = {}
    if numeric_formats is None:
        return resolved
    for position_key, spec in numeric_formats.items():
        canonical_name = position_to_canonical.get(position_key)
        if canonical_name is None:
            continue
        resolved[canonical_name] = spec
    return resolved
