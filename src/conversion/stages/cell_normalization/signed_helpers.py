"""Signed value SQL fragment helpers used by cell normalization transforms."""

from __future__ import annotations

import re

from conversion.stages.cell_normalization.currency_helpers import (
    build_currency_symbol_stripped_expr,
)
from conversion.stages.cell_normalization.sql_helpers import quote_string


def _marker_has_expr(trimmed: str, marker: str) -> str:
    m = re.escape(marker.lower())
    at_start = f"REGEXP_FULL_MATCH(LOWER({trimmed}), {quote_string(rf'^{m}\s*.+$')})"
    at_end = f"REGEXP_FULL_MATCH(LOWER({trimmed}), {quote_string(rf'^.+\s*{m}$')})"
    return f"({at_start} OR {at_end})"


def _marker_strip_expr(trimmed: str, marker: str) -> str:
    m = re.escape(marker.lower())
    at_start = f"REGEXP_FULL_MATCH(LOWER({trimmed}), {quote_string(rf'^{m}\s*.+$')})"
    from_start = f"TRIM(REGEXP_REPLACE(LOWER({trimmed}), {quote_string(rf'^{m}\s*')}, ''))"
    from_end = f"TRIM(REGEXP_REPLACE(LOWER({trimmed}), {quote_string(rf'\s*{m}$')}, ''))"
    return f"CASE WHEN {at_start} THEN {from_start} ELSE {from_end} END"


def build_signed_value_expr(
    value_expr: str,
    *,
    positive_markers: tuple[str, ...],
    negative_markers: tuple[str, ...],
    parentheses_as_negative: bool,
) -> str:
    """Normalize a signed value to a plain signed decimal string."""
    trimmed = f"TRIM({value_expr})"
    cases = []
    for marker in negative_markers:
        stripped = build_currency_symbol_stripped_expr(_marker_strip_expr(trimmed, marker))
        cases.append(f"WHEN {_marker_has_expr(trimmed, marker)} THEN '-' || {stripped}")
    for marker in positive_markers:
        stripped = build_currency_symbol_stripped_expr(_marker_strip_expr(trimmed, marker))
        cases.append(f"WHEN {_marker_has_expr(trimmed, marker)} THEN {stripped}")
    if parentheses_as_negative:
        inner = f"TRIM(SUBSTRING({trimmed}, 2, LENGTH({trimmed}) - 2))"
        cases.append(
            f"WHEN REGEXP_FULL_MATCH({trimmed}, {quote_string(r'^\(.+\)$')}) "
            f"THEN '-' || {build_currency_symbol_stripped_expr(inner)}"
        )
    else_expr = build_currency_symbol_stripped_expr(trimmed)
    if not cases:
        return else_expr
    return "CASE " + " ".join(cases) + f" ELSE {else_expr} END"
