"""ISO standardized-code sets derived from pycountry."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

import pycountry

from shared.db.sql import quote_string

CodeCase = Literal["upper", "lower"]


def _values(records: Iterable[object], attr: str, case: CodeCase) -> frozenset[str]:
    transform = str.upper if case == "upper" else str.lower
    return frozenset(
        transform(value)
        for record in records
        if (value := getattr(record, attr, None))
    )


COUNTRY_ALPHA2_CODES = _values(pycountry.countries, "alpha_2", "upper")
COUNTRY_ALPHA3_CODES = _values(pycountry.countries, "alpha_3", "upper")
CURRENCY_ALPHA3_CODES = _values(pycountry.currencies, "alpha_3", "upper")
LANGUAGE_ALPHA2_CODES = _values(pycountry.languages, "alpha_2", "lower")
LANGUAGE_ALPHA3_CODES = _values(pycountry.languages, "alpha_3", "lower")


def country_codes(code_format: Literal["alpha_2", "alpha_3"]) -> frozenset[str]:
    """Return valid ISO 3166-1 country codes for the declared format."""
    if code_format == "alpha_2":
        return COUNTRY_ALPHA2_CODES
    return COUNTRY_ALPHA3_CODES


def currency_codes() -> frozenset[str]:
    """Return valid ISO 4217 alpha-3 currency codes."""
    return CURRENCY_ALPHA3_CODES


def language_codes(code_format: Literal["alpha_2", "alpha_3"]) -> frozenset[str]:
    """Return valid ISO 639 language codes for the declared format."""
    if code_format == "alpha_2":
        return LANGUAGE_ALPHA2_CODES
    return LANGUAGE_ALPHA3_CODES


def sql_in_list(values: Iterable[str]) -> str:
    """Return a deterministic SQL IN-list payload for standardized code validation."""
    return ", ".join(quote_string(value) for value in sorted(values))
