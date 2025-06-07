"""Inference rules for selecting a normalized column type."""

from __future__ import annotations

from normalize.stages.shared_profiling import ColumnProfile


def infer_column_type(
    profile: ColumnProfile,
    *,
    numeric_threshold: float,
    boolean_threshold: float,
) -> str:
    """
    Infer one column type using profile ratios and strict boolean policy.

    Rule order:
    - empty -> string
    - boolean if boolean ratio >= boolean_threshold
    - integer if integer ratio >= numeric_threshold
    - decimal if decimal ratio >= numeric_threshold
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
    return "string"
