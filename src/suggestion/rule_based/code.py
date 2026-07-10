"""Standardized-code detection for rule-based column type inference."""

from __future__ import annotations

import re
from collections.abc import Sequence

from shared.models.column import (
    ColumnConfig,
    CountryCodeColumnConfig,
    CurrencyCodeColumnConfig,
    LanguageCodeColumnConfig,
)
from shared.parsing.iso_codes import country_codes, currency_codes, language_codes

from suggestion.rule_based.constants import CODE_MATCH_MIN_RATIO

_CODE_RE = re.compile(r"^[A-Za-z]{2,3}$")


def _normalized_code(value: str, case: str) -> str | None:
    stripped = value.strip()
    if _CODE_RE.fullmatch(stripped) is None:
        return None
    return stripped.upper() if case == "upper" else stripped.lower()


def _match_count(values: Sequence[str], allowed_codes: frozenset[str], case: str) -> int:
    count = 0
    for value in values:
        normalized = _normalized_code(value, case)
        if normalized is not None and normalized in allowed_codes:
            count += 1
    return count


def infer_code_type(values: Sequence[str], sample_count: int) -> ColumnConfig | None:
    """Return a best-fit standardized-code config, or None if no code type fits."""
    candidates: tuple[tuple[int, ColumnConfig], ...] = (
        (
            _match_count(values, currency_codes(), "upper"),
            CurrencyCodeColumnConfig(),
        ),
        (
            _match_count(values, country_codes("alpha_2"), "upper"),
            CountryCodeColumnConfig(code_format="alpha_2"),
        ),
        (
            _match_count(values, country_codes("alpha_3"), "upper"),
            CountryCodeColumnConfig(code_format="alpha_3"),
        ),
        (
            _match_count(values, language_codes("alpha_2"), "lower"),
            LanguageCodeColumnConfig(code_format="alpha_2"),
        ),
        (
            _match_count(values, language_codes("alpha_3"), "lower"),
            LanguageCodeColumnConfig(code_format="alpha_3"),
        ),
    )
    best_count, best_config = max(
        candidates,
        key=lambda item: (item[0], -_priority(item[1])),
    )
    if best_count / sample_count >= CODE_MATCH_MIN_RATIO:
        return best_config
    return None


def _priority(config: ColumnConfig) -> int:
    """Return deterministic tiebreak priority; lower wins."""
    order = {
        "currency_code": 0,
        "country_code": 1,
        "language_code": 2,
    }
    return order.get(config.type, 99)
