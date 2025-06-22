"""Schema validation helpers for cell normalization."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from normalize.core.column_config import ColumnConfig, column_config_type

AUDIT_COLUMNS = {
    "_row_index",
    "_global_row_index",
    "_raw_row",
    "_parse_issues",
    "_parse_error_count",
}


def validate_column_config(
    column_config: Mapping[str, ColumnConfig],
    data_columns: Sequence[str],
) -> None:
    """Ensure every data column has a declared config entry."""
    missing = [column for column in data_columns if column not in column_config]
    if missing:
        raise ValueError(f"MISSING_COLUMN_CONFIG:{','.join(sorted(missing))}")
    extras = [column for column in column_config if column not in data_columns]
    if extras:
        raise ValueError(f"UNKNOWN_COLUMN_CONFIG:{','.join(sorted(extras))}")
    unsupported = sorted(
        {
            column_config_type(spec)
            for spec in column_config.values()
            if column_config_type(spec)
            not in {"string", "boolean", "integer", "decimal", "currency", "date"}
        }
    )
    if unsupported:
        raise ValueError(f"UNSUPPORTED_COLUMN_TYPES:{','.join(unsupported)}")
