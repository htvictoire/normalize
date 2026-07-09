"""Column value sampling from pre-parsed rows."""

from __future__ import annotations

from collections.abc import Mapping

from shared.ingestion.cell import normalize_cell_value

from suggestion.rule_based.constants import INFERENCE_SAMPLES_PER_COLUMN


def sample_column_values(
    rows: list[list[str]],
    position_to_name: Mapping[str, str],
) -> dict[str, list[str]]:
    """Collect up to INFERENCE_SAMPLES_PER_COLUMN non-null values per column position."""
    positions = list(position_to_name.keys())
    result: dict[str, list[str]] = {position: [] for position in positions}
    full_columns = 0
    total_columns = len(positions)
    for row in rows:
        if full_columns == total_columns:
            break
        for index, position in enumerate(positions):
            col_values = result[position]
            if len(col_values) >= INFERENCE_SAMPLES_PER_COLUMN:
                continue
            value = normalize_cell_value(row[index])
            if value is not None:
                col_values.append(value)
                if len(col_values) == INFERENCE_SAMPLES_PER_COLUMN:
                    full_columns += 1
    return result
