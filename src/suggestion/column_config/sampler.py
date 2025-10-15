"""Column value sampling from pre-parsed rows."""

from __future__ import annotations

from collections.abc import Sequence

from shared.utils.values import normalize_cell_value
from suggestion.constants import INFERENCE_SAMPLES_PER_COLUMN


def sample_column_values(
    rows: list[list[str]],
    columns: Sequence[str],
) -> dict[str, list[str]]:
    """Collect up to INFERENCE_SAMPLES_PER_COLUMN non-null values per column."""
    result: dict[str, list[str]] = {col: [] for col in columns}
    full_columns = 0
    total_columns = len(columns)
    for row in rows:
        if full_columns == total_columns:
            break
        for index, col_name in enumerate(columns):
            col_values = result[col_name]
            if len(col_values) >= INFERENCE_SAMPLES_PER_COLUMN:
                continue
            value = normalize_cell_value(row[index])
            if value is not None:
                col_values.append(value)
                if len(col_values) == INFERENCE_SAMPLES_PER_COLUMN:
                    full_columns += 1
    return result
