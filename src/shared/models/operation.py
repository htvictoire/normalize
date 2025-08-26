"""Shared operation and source-format models."""

from __future__ import annotations

from typing import Literal

from shared.models.base import MainModel

HeaderMode = Literal["present", "absent"]
TraceMode = Literal["full", "sparse"]
RunMode = Literal["PROFILE", "APPLY"]


class SourceFormatConfig(MainModel):
    """Caller-declared source format settings."""

    encoding: str
    delimiter: str
    header_mode: HeaderMode
    header_row_index: int | None


class DecisionThresholds(MainModel):
    """Readiness thresholds for decision evaluation."""

    ready: float
    warning: float


class OperationConfig(MainModel):
    """Confirmed operation flags and token policy."""

    null_tokens: tuple[str, ...]
    assign_indices: bool
    drop_empty_rows: bool
    emit_raw_row: bool
    full_raw_row: bool
    emit_parse_issues: bool
    include_unique_ratio: bool
    include_per_column_parse_error_counts: bool
    approximate_unique: bool
    trace_mode: TraceMode
    decision_thresholds: DecisionThresholds
