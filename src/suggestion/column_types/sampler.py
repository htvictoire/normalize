"""Sampling and orchestration of per-column type inference."""

from __future__ import annotations

from collections.abc import Sequence

from duckdb import DuckDBPyConnection

from suggestion.column_types.types import infer_column_type
from suggestion.constants import (
    CROSS_COLUMN_MAJORITY_MIN_EVIDENCED,
    INFERENCE_RESERVOIR_ROWS,
    INFERENCE_SAMPLE_SEED,
    INFERENCE_SAMPLES_PER_COLUMN,
    NUMERIC_TYPES,
)
from suggestion.column_types.models import NumericSuggestion


def infer_types_from_sample(
    conn: DuckDBPyConnection,
    *,
    table_name: str,
    columns: Sequence[str],
    sample_rows: int = INFERENCE_RESERVOIR_ROWS,
    samples_per_column: int = INFERENCE_SAMPLES_PER_COLUMN,
) -> tuple[dict[str, str], dict[str, str], dict[str, NumericSuggestion]]:
    """Sample rows and infer column types/date formats/numeric settings."""
    if sample_rows <= 0:
        raise ValueError("sample_rows must be positive")
    if samples_per_column <= 0:
        raise ValueError("samples_per_column must be positive")

    sampled_rows = conn.execute(
        f"SELECT * FROM {table_name} "
        f"USING SAMPLE reservoir({int(sample_rows)} ROWS) REPEATABLE ({INFERENCE_SAMPLE_SEED})"
    ).fetchall()
    sampled_values: dict[str, list[str]] = {column_name: [] for column_name in columns}
    for row in sampled_rows:
        for index, column_name in enumerate(columns):
            if len(sampled_values[column_name]) >= samples_per_column:
                continue
            normalized = normalize_sample_value(row[index])
            if normalized is None:
                continue
            sampled_values[column_name].append(normalized)

    inferred_types: dict[str, str] = {}
    inferred_date_formats: dict[str, str] = {}
    inferred_numeric_suggestions: dict[str, NumericSuggestion] = {}
    for column_name, values in sampled_values.items():
        inferred_type, date_format, numeric = infer_column_type(values)
        inferred_types[column_name] = inferred_type
        if date_format is not None:
            inferred_date_formats[column_name] = date_format
        if numeric is not None:
            inferred_numeric_suggestions[column_name] = numeric

    _apply_separator_consistency(inferred_types, inferred_numeric_suggestions)
    return inferred_types, inferred_date_formats, inferred_numeric_suggestions


def _apply_separator_consistency(
    inferred_types: dict[str, str],
    inferred_numeric_suggestions: dict[str, NumericSuggestion],
) -> None:
    """Align decimal separators of low-evidence columns to the file-level majority."""
    evidenced = [
        s.decimal_separator
        for col, s in inferred_numeric_suggestions.items()
        if inferred_types.get(col) in NUMERIC_TYPES and s.separator_evidence > 0
    ]
    if len(evidenced) < CROSS_COLUMN_MAJORITY_MIN_EVIDENCED:
        return

    dot_count = evidenced.count(".")
    comma_count = evidenced.count(",")
    if dot_count >= 2 * comma_count:
        file_decimal = "."
    elif comma_count >= 2 * dot_count:
        file_decimal = ","
    else:
        return

    for col in list(inferred_numeric_suggestions):
        if inferred_types.get(col) not in NUMERIC_TYPES:
            continue
        s = inferred_numeric_suggestions[col]
        if s.separator_evidence > 0 or s.decimal_separator == file_decimal:
            continue
        if s.thousand_separator == file_decimal:
            continue
        inferred_numeric_suggestions[col] = NumericSuggestion(
            decimal_separator=file_decimal,
            thousand_separator=s.thousand_separator,
            grouping_style=s.grouping_style,
            allow_leading_decimal_point=s.allow_leading_decimal_point,
            separator_evidence=s.separator_evidence,
        )


def normalize_sample_value(value: object) -> str | None:
    """Normalize sampled scalar value into a non-empty stripped string."""
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    return normalized
