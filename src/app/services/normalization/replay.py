"""Replay config serialization from instance state."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from app.models.instance import InstanceModel
from shared.models.column import ColumnConfig, serialize_column_config_map
from shared.models.operation import OperationConfig


def build_instance_replay_config(
    instance: InstanceModel,
    confirmed_column_config: Mapping[str, ColumnConfig],
) -> dict[str, Any]:
    operation = cast(OperationConfig, instance.operation_config)
    return {
        "source_format": {
            "encoding": instance.source_format.encoding,
            "delimiter": instance.source_format.delimiter,
            "header_mode": instance.source_format.header_mode,
            "header_row_index": instance.source_format.header_row_index,
        },
        "confirmed_column_config": serialize_column_config_map(confirmed_column_config),
        "operation_config": {
            "null_tokens": list(operation.null_tokens),
            "boolean_true_tokens": list(operation.boolean_true_tokens),
            "boolean_false_tokens": list(operation.boolean_false_tokens),
            "assign_indices": operation.assign_indices,
            "drop_empty_rows": operation.drop_empty_rows,
            "emit_raw_row": operation.emit_raw_row,
            "full_raw_row": operation.full_raw_row,
            "emit_parse_issues": operation.emit_parse_issues,
            "include_unique_ratio": operation.include_unique_ratio,
            "include_per_column_parse_error_counts": (
                operation.include_per_column_parse_error_counts
            ),
            "approximate_unique": operation.approximate_unique,
            "trace_mode": operation.trace_mode,
            "decision_thresholds": {
                "ready": operation.decision_thresholds.ready,
                "warning": operation.decision_thresholds.warning,
            },
        },
    }
