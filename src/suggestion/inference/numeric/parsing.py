"""Numeric token parsing primitives."""

from __future__ import annotations

from shared.models.column import GroupingStyle
from suggestion.constants import (
    GROUP_FIRST_MAX_DIGITS,
    GROUP_INDIAN_MIDDLE_SIZE,
    GROUP_INDIAN_TWO_GROUP_CASE,
    GROUP_WESTERN_SIZE,
)
from suggestion.models import NumericCandidate, NumericParseResult


def parse_numeric_token(
    value: str,
    *,
    candidate: NumericCandidate,
) -> NumericParseResult | None:
    """Try parsing one numeric token under one candidate format."""
    stripped_sign = strip_numeric_sign(value)
    if stripped_sign is None:
        return None
    stripped, negative = stripped_sign

    decimal_separator = candidate.decimal_separator
    thousand_separator = candidate.thousand_separator
    used_decimal_separator = decimal_separator in stripped
    used_thousand_separator = bool(thousand_separator) and thousand_separator in stripped
    leading_decimal_point = False

    parse_ok = stripped.count(decimal_separator) <= 1
    integer_part_raw = stripped
    fractional_part: str | None = None
    if parse_ok and decimal_separator in stripped:
        integer_part_raw, fractional_part = stripped.split(decimal_separator, 1)

    if parse_ok and not valid_grouping(
        integer_part_raw,
        thousand_separator=thousand_separator,
        grouping_style=candidate.grouping_style,
    ):
        parse_ok = False

    integer_digits = (
        integer_part_raw.replace(thousand_separator, "")
        if thousand_separator
        else integer_part_raw
    )
    if parse_ok and not integer_digits and fractional_part is None:
        parse_ok = False
    elif parse_ok and not integer_digits:
        leading_decimal_point = True
        integer_digits = "0"
    if parse_ok and not integer_digits.isdigit():
        parse_ok = False

    if fractional_part is not None:
        if parse_ok and fractional_part and fractional_part.isdigit():
            normalized = f"{integer_digits}.{fractional_part}"
        else:
            parse_ok = False
            normalized = ""
    elif parse_ok:
        normalized = integer_digits
    else:
        normalized = ""

    if not parse_ok:
        return None

    if negative:
        normalized = f"-{normalized}"
    return NumericParseResult(
        normalized=normalized,
        used_decimal_separator=used_decimal_separator,
        used_thousand_separator=used_thousand_separator,
        leading_decimal_point=leading_decimal_point,
    )


def strip_numeric_sign(value: str) -> tuple[str, bool] | None:
    """Strip numeric sign/accounting sign and return clean value + negativity flag."""
    stripped = value.strip().replace(" ", "")
    if not stripped:
        return None

    negative = False
    if stripped.startswith("(") and stripped.endswith(")"):
        stripped = stripped[1:-1]
        negative = True
    if stripped.startswith("+"):
        stripped = stripped[1:]
    if stripped.startswith("-"):
        stripped = stripped[1:]
        negative = True
    if not stripped:
        return None
    return stripped, negative


def valid_grouping(
    integer_part: str,
    *,
    thousand_separator: str,
    grouping_style: GroupingStyle,
) -> bool:
    """Validate integer grouping by selected grouping style."""
    is_valid = True
    if not integer_part:
        is_valid = True
    elif not thousand_separator or thousand_separator not in integer_part:
        is_valid = integer_part.isdigit()
    else:
        groups = integer_part.split(thousand_separator)
        if any((not group) or (not group.isdigit()) for group in groups) or not 1 <= len(
            groups[0]
        ) <= GROUP_FIRST_MAX_DIGITS:
            is_valid = False
        elif grouping_style == "western":
            is_valid = all(len(group) == GROUP_WESTERN_SIZE for group in groups[1:])
        elif len(groups[-1]) != GROUP_WESTERN_SIZE:
            is_valid = False
        elif len(groups) == GROUP_INDIAN_TWO_GROUP_CASE:
            is_valid = True
        else:
            is_valid = all(len(group) == GROUP_INDIAN_MIDDLE_SIZE for group in groups[1:-1])
    return is_valid
