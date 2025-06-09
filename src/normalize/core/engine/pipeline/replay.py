"""Replay configuration helpers for pipeline manifest/fingerprint payloads."""

from __future__ import annotations

from typing import Any

from normalize.core.engine.config import EngineConfig


def build_replay_config(effective: EngineConfig) -> dict[str, Any]:
    """Build deterministic replay config payload from effective runtime settings."""
    return {
        "header_mode": effective.header_mode.value,
        "header_row_index": effective.header_row_index,
        "encoding": effective.encoding,
        "delimiter": effective.delimiter,
        "decimal_separator": effective.decimal_separator,
        "thousand_separator": effective.thousand_separator,
        "allow_leading_decimal_point": effective.allow_leading_decimal_point,
        "date_formats": dict(effective.date_formats),
        "null_tokens": list(effective.null_tokens),
        "boolean_true_tokens": list(effective.boolean_true_tokens),
        "boolean_false_tokens": list(effective.boolean_false_tokens),
        "type_inference_numeric_threshold": effective.type_inference_numeric_threshold,
        "type_inference_boolean_threshold": effective.type_inference_boolean_threshold,
        "assign_indices": effective.assign_indices,
        "drop_empty_rows": effective.drop_empty_rows,
        "full_raw_row": effective.full_raw_row,
        "emit_raw_row": effective.emit_raw_row,
        "emit_parse_issues": effective.emit_parse_issues,
        "include_unique_ratio": effective.include_unique_ratio,
        "include_per_column_parse_error_counts": effective.include_per_column_parse_error_counts,
        "approximate_unique": effective.approximate_unique,
        "decision_ready_threshold": effective.decision_ready_threshold,
        "decision_warning_threshold": effective.decision_warning_threshold,
        "trace_mode": effective.trace_mode,
    }
