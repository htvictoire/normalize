"""Schema validation helpers for cell normalization."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from normalize.stages.type_inference import SUPPORTED_INFERRED_TYPES

AUDIT_COLUMNS = {
    "_row_index",
    "_global_row_index",
    "_raw_row",
    "_parse_issues",
    "_parse_error_count",
}


def validate_inferred_types(
    inferred_types: Mapping[str, str],
    data_columns: Sequence[str],
) -> None:
    """Ensure every data column has a known inferred type."""
    missing = [column for column in data_columns if column not in inferred_types]
    if missing:
        raise ValueError(f"MISSING_INFERRED_TYPES:{','.join(sorted(missing))}")
    unknown_types = sorted(
        {value for value in inferred_types.values() if value not in SUPPORTED_INFERRED_TYPES}
    )
    if unknown_types:
        raise ValueError(f"UNSUPPORTED_INFERRED_TYPES:{','.join(unknown_types)}")
