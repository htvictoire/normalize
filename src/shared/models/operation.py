"""Shared operation and source-format models."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from shared.models.base import MainModel

HeaderMode = Literal["present", "absent"]
TraceMode = Literal["full", "sparse"]
FileFormat = Literal["csv", "excel", "json"]
FileSource = Literal["local", "s3"]
SuggestionMethod = Literal["rule_based", "ai"]
AiProvider = Literal["claude", "openai", "gemini"]


class CsvSourceFormat(MainModel):
    """Source format settings for CSV files."""

    format_type: Literal["csv"] = "csv"
    encoding: str
    delimiter: str
    header_mode: HeaderMode
    header_row_index: int | None


class ExcelSourceFormat(MainModel):
    """Source format settings for Excel files (.xlsx only)."""

    format_type: Literal["excel"] = "excel"
    sheet_name: str | None = None
    header_mode: HeaderMode
    header_row_index: int | None


class JsonSourceFormat(MainModel):
    """Source format settings for JSON files."""

    format_type: Literal["json"] = "json"


SourceFormat = Annotated[
    CsvSourceFormat | ExcelSourceFormat | JsonSourceFormat,
    Field(discriminator="format_type"),
]


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

