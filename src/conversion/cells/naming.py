"""Naming helpers for cell normalization internals."""

from __future__ import annotations


def issue_alias(column_name: str) -> str:
    """Return deterministic temporary issue-column alias for one data column."""
    return f"__issue__{column_name}"


def parse_match_alias(column_name: str) -> str:
    """Alias for the pre-computed REGEXP_FULL_MATCH boolean in the parse CTE."""
    return f"__p_match__{column_name}"


def parse_cast_alias(column_name: str) -> str:
    """Alias for the pre-computed TRY_CAST numeric result in the parse CTE."""
    return f"__p_cast__{column_name}"


def parse_date_alias(column_name: str) -> str:
    """Alias for the pre-computed TRY_CAST date result in the parse CTE."""
    return f"__p_date__{column_name}"


def parse_datetime_alias(column_name: str) -> str:
    """Alias for the pre-computed TRY_CAST timestamp result in the parse CTE."""
    return f"__p_datetime__{column_name}"


def parse_time_alias(column_name: str) -> str:
    """Alias for the pre-computed TRY_CAST time result in the parse CTE."""
    return f"__p_time__{column_name}"


def parse_raw_alias(column_name: str) -> str:
    """Alias for the pre-computed raw VARCHAR cell value in the parse CTE."""
    return f"__p_raw__{column_name}"


def parse_lower_alias(column_name: str) -> str:
    """Alias for the pre-computed lower/trimmed cell value in the parse CTE."""
    return f"__p_lower__{column_name}"


def parse_nullish_alias(column_name: str) -> str:
    """Alias for the pre-computed nullish predicate in the parse CTE."""
    return f"__p_nullish__{column_name}"
