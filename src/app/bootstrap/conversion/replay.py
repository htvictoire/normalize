"""Replay config serialization from confirmed run configuration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from shared.models.column import ColumnConfig, serialize_column_config_map
from shared.models.operation import (
    CsvSourceFormat,
    ExcelSourceFormat,
    JsonSourceFormat,
    OperationConfig,
)


def build_replay_config(
    source_format: CsvSourceFormat | ExcelSourceFormat | JsonSourceFormat,
    operation_config: OperationConfig,
    confirmed_column_config: Mapping[str, ColumnConfig],
) -> dict[str, Any]:
    return {
        "source_format": source_format.model_dump(),
        "confirmed_column_config": serialize_column_config_map(confirmed_column_config),
        "operation_config": {
            "null_tokens": list(operation_config.null_tokens),
            "assign_indices": operation_config.assign_indices,
            "drop_empty_rows": operation_config.drop_empty_rows,
            "emit_raw_row": operation_config.emit_raw_row,
            "full_raw_row": operation_config.full_raw_row,
            "emit_parse_issues": operation_config.emit_parse_issues,
            "include_unique_ratio": operation_config.include_unique_ratio,
            "include_per_column_parse_error_counts": (
                operation_config.include_per_column_parse_error_counts
            ),
            "approximate_unique": operation_config.approximate_unique,
            "trace_mode": operation_config.trace_mode,
            "decision_thresholds": {
                "ready": operation_config.decision_thresholds.ready,
                "warning": operation_config.decision_thresholds.warning,
            },
        },
    }
