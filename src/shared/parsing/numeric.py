"""Locale-agnostic numeric parsing — regex validation and SQL value normalization.

A single numeric column routinely carries more than one locale: an export mixing
``$17,300.50`` with ``NOK 13.444,33`` is ordinary, not pathological. A column
therefore declares no separators at all; the decimal separator is resolved *per
value* from the value's own shape.

Resolution rules, in order:

1. Both ``.`` and ``,`` present → the **last** one is the decimal separator.
   ``1.234,56`` → comma decimal.  ``1,234.56`` → dot decimal.
2. One separator, repeated → it is grouping; there is no decimal part.
3. One separator, not followed by exactly 3 digits → it is the decimal.
   ``0,0007`` and ``2,23`` can only be decimals.
4. One separator followed by exactly 3 digits, integer part a lone zero → decimal.
   Grouping never follows a bare zero: ``0,014`` is 0.014, not 14.
5. Otherwise → grouping. ``1,234`` is 1234.

Rule 5 is the only genuine ambiguity (a European writing ``1,234`` to mean 1.234)
and resolves toward grouping, which is the overwhelmingly common intent.

Apostrophes and spaces are never decimal separators, so they are stripped as
grouping before any rule applies (``1'234.56``, ``1 234,56``).
"""

from __future__ import annotations

from shared.db.sql import quote_string

# Separators that can only ever mean grouping: apostrophe, space, NBSP, narrow NBSP.
_GROUP_ONLY_CHARS: tuple[str, ...] = ("'", " ", "\u00a0", "\u202f")
_GROUP_ONLY_CLASS = "['\u0020\u00a0\u202f]"

# Integer shapes, one alternative per grouping convention. RE2 has no
# backreferences, so separator consistency is expressed by enumerating shapes.
_WESTERN_GROUPED = r"[0-9]{1,3}(?:,[0-9]{3})+"
_EUROPEAN_GROUPED = r"[0-9]{1,3}(?:\.[0-9]{3})+"
_INDIAN_GROUPED = r"[0-9]{1,2}(?:,[0-9]{2})+,[0-9]{3}"
_UNGROUPED = r"[0-9]+"


def strip_group_only_chars(value: str) -> str:
    """Remove separators that can never be decimals (apostrophe, spaces)."""
    for char in _GROUP_ONLY_CHARS:
        value = value.replace(char, "")
    return value


def decimal_pattern_regex() -> str:
    """Return a regex matching a valid decimal in any supported locale.

    Applied to values whose group-only characters are already removed. Malformed
    grouping (``1,2,3.45``, ``12,3456.7``) matches no alternative and is rejected:
    dropping declared separators does not mean dropping validation.

    A leading decimal point (``.5``, ``,5``) is accepted as an unambiguous ``0.5``.

    Exponent/scientific notation (``1.5e10``) is intentionally not matched and is
    reported as a parse issue rather than converted: the stored decimal type is sized
    from a value's literal digits, which exponent notation does not express. This is
    a deliberate scope limit, not a validation gap.
    """
    alternatives = [
        rf"{_WESTERN_GROUPED}(?:\.[0-9]*)?",
        rf"{_EUROPEAN_GROUPED}(?:,[0-9]*)?",
        rf"{_INDIAN_GROUPED}(?:\.[0-9]*)?",
        rf"{_UNGROUPED}(?:[.,][0-9]*)?",
        r"[.,][0-9]+",
    ]
    return rf"^[+-]?(?:{'|'.join(alternatives)})$"


def integer_pattern_regex() -> str:
    """Return a regex matching a valid integer in any supported locale."""
    alternatives = [_WESTERN_GROUPED, _EUROPEAN_GROUPED, _INDIAN_GROUPED, _UNGROUPED]
    return rf"^[+-]?(?:{'|'.join(alternatives)})$"


def strip_group_only_sql(value_expr: str) -> str:
    """SQL: drop apostrophes and spaces, which are never decimal separators."""
    return f"REGEXP_REPLACE({value_expr}, {quote_string(_GROUP_ONLY_CLASS)}, '', 'g')"


def _count_sql(value_expr: str, char: str) -> str:
    literal = quote_string(char)
    return f"(LENGTH({value_expr}) - LENGTH(REPLACE({value_expr}, {literal}, '')))"


def _last_index_sql(value_expr: str, char: str) -> str:
    """SQL: 1-based index of the last occurrence of char, or 0 when absent."""
    literal = quote_string(char)
    return (
        f"CASE WHEN STRPOS({value_expr}, {literal}) = 0 THEN 0 "
        f"ELSE LENGTH({value_expr}) - STRPOS(REVERSE({value_expr}), {literal}) + 1 END"
    )


def _lone_separator_is_decimal_sql(value_expr: str, last_index: str) -> str:
    """SQL: rules 3 and 4 — is a single separator a decimal rather than grouping?"""
    tail_length = f"(LENGTH({value_expr}) - {last_index})"
    integer_part = f"SUBSTRING({value_expr}, 1, {last_index} - 1)"
    integer_part_is_zero = f"REGEXP_FULL_MATCH({integer_part}, {quote_string('^[+-]?0?$')})"
    return f"({tail_length} <> 3 OR {integer_part_is_zero})"


def comma_is_decimal_sql(cleaned_expr: str) -> str:
    """SQL predicate: this value uses ``,`` as its decimal separator (european).

    ``cleaned_expr`` must already have passed through ``strip_group_only_sql``.
    Callers hoist that into a single materialised alias — re-deriving it inside
    every predicate makes DuckDB run the REGEXP_REPLACE once per reference.
    """
    dot_count = _count_sql(cleaned_expr, ".")
    comma_count = _count_sql(cleaned_expr, ",")
    last_dot = _last_index_sql(cleaned_expr, ".")
    last_comma = _last_index_sql(cleaned_expr, ",")
    return (
        f"(({dot_count} > 0 AND {comma_count} > 0 AND {last_comma} > {last_dot}) "
        f"OR ({comma_count} = 1 AND {dot_count} = 0 "
        f"AND {_lone_separator_is_decimal_sql(cleaned_expr, last_comma)}))"
    )


def dot_is_decimal_sql(cleaned_expr: str) -> str:
    """SQL predicate: this value uses ``.`` as its decimal separator (western).

    ``cleaned_expr`` must already have passed through ``strip_group_only_sql``.
    """
    dot_count = _count_sql(cleaned_expr, ".")
    comma_count = _count_sql(cleaned_expr, ",")
    last_dot = _last_index_sql(cleaned_expr, ".")
    last_comma = _last_index_sql(cleaned_expr, ",")
    return (
        f"(({dot_count} > 0 AND {comma_count} > 0 AND {last_dot} > {last_comma}) "
        f"OR ({dot_count} = 1 AND {comma_count} = 0 "
        f"AND {_lone_separator_is_decimal_sql(cleaned_expr, last_dot)}))"
    )


def decimal_separator_sql(cleaned_expr: str) -> str:
    """SQL: the decimal separator this value uses — ``','``, ``'.'`` or ``''`` for none."""
    return (
        f"CASE WHEN {comma_is_decimal_sql(cleaned_expr)} THEN ',' "
        f"WHEN {dot_is_decimal_sql(cleaned_expr)} THEN '.' "
        f"ELSE '' END"
    )


def decimal_normalize_sql(cleaned_expr: str) -> str:
    """SQL: resolve the locale per value, returning a plain ``.``-decimal string.

    ``cleaned_expr`` must already have currency symbols, sign markers and
    group-only characters stripped.
    """
    comma_decimal = f"REPLACE(REPLACE({cleaned_expr}, '.', ''), ',', '.')"
    dot_decimal = f"REPLACE({cleaned_expr}, ',', '')"
    all_grouping = f"REPLACE(REPLACE({cleaned_expr}, ',', ''), '.', '')"
    return (
        f"CASE WHEN {comma_is_decimal_sql(cleaned_expr)} THEN {comma_decimal} "
        f"WHEN {dot_is_decimal_sql(cleaned_expr)} THEN {dot_decimal} "
        f"ELSE {all_grouping} END"
    )


def integer_normalize_sql(cleaned_expr: str) -> str:
    """SQL: strip every grouping separator from an integer value."""
    return f"REPLACE(REPLACE({cleaned_expr}, ',', ''), '.', '')"


def has_significant_digit_sql(value_expr: str) -> str:
    """SQL predicate: this value carries a digit other than zero.

    Separates a source zero from a quantity a narrower type rounded away to zero —
    ``0.00`` and ``0.00000000000000000035`` are indistinguishable once stored, and
    only the second lost anything.
    """
    return f"REGEXP_MATCHES({value_expr}, {quote_string('[1-9]')})"


def significant_scale_sql(normalized_expr: str) -> str:
    """SQL: how many fractional digits this value actually carries.

    ``normalized_expr`` must be the output of ``decimal_normalize_sql`` — a plain
    ``.``-decimal string with at most one separator.

    Trailing zeros do not count: ``1.500`` carries one fractional digit, not three.
    Padding a fraction with zeros changes no digit, so a column sized to hold it at
    scale 1 holds it exactly.
    """
    point = f"STRPOS({normalized_expr}, '.')"
    return (
        f"CASE WHEN {point} = 0 THEN 0 "
        f"ELSE LENGTH(RTRIM({normalized_expr}, '0')) - {point} END"
    )


def integer_digits_sql(normalized_expr: str) -> str:
    """SQL: how many digits this value carries before the decimal point.

    Leading zeros do not count and neither does the sign: ``-007.5`` needs one
    integer digit, and ``0.5`` needs none.
    """
    point = f"STRPOS({normalized_expr}, '.')"
    integer_part = (
        f"CASE WHEN {point} = 0 THEN {normalized_expr} "
        f"ELSE SUBSTRING({normalized_expr}, 1, {point} - 1) END"
    )
    return f"LENGTH(LTRIM(LTRIM({integer_part}, '+-'), '0'))"
