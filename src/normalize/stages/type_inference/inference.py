"""Inference rules for selecting a normalized column type."""

from __future__ import annotations

from normalize.stages.shared_profiling import ColumnProfile


def infer_column_type(
    profile: ColumnProfile,
    *,
    numeric_threshold: float,
    boolean_threshold: float,
    currency_threshold: float,
) -> str:
    """
    Infer one column type using profile ratios and strict boolean policy.

    Rule order:
    - empty -> string
    - boolean if boolean ratio >= boolean_threshold
    - integer if integer ratio >= numeric_threshold
    - decimal if decimal ratio >= numeric_threshold
    - currency if currency ratio >= currency_threshold
    - otherwise string
    """
    if profile.non_empty_count <= 0:
        return "string"
    if profile.bool_ratio >= boolean_threshold:
        return "boolean"
    if profile.int_ratio >= numeric_threshold:
        return "integer"
    if profile.decimal_ratio >= numeric_threshold:
        return "decimal"
    # Only classify as currency when there are rows with actual currency-specific
    # content (tokens or accounting notation). If currency_ratio == decimal_ratio,
    # all "currency" matches are plain decimals that just cleared the lower
    # threshold — don't misclassify a messy decimal column as currency.
    if (
        profile.currency_ratio >= currency_threshold
        and profile.currency_ratio > profile.decimal_ratio
    ):
        return "currency"
    return "string"
