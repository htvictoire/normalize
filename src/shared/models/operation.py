"""Shared operation and source-format models."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

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
    """Readiness thresholds for decision evaluation, as quality scores in [0, 100]."""

    ready: float = Field(ge=0.0, le=100.0)
    warning: float = Field(ge=0.0, le=100.0)

    @model_validator(mode="after")
    def _warning_not_above_ready(self) -> DecisionThresholds:
        """Reject inverted thresholds.

        A score below `warning` is BLOCKED and a score below `ready` is
        READY_WITH_WARNINGS, so `warning > ready` inverts the gate into one that
        blocks nearly everything — silently, since both bounds are individually legal.
        """
        if self.warning > self.ready:
            raise ValueError(
                f"decision thresholds must satisfy warning <= ready, "
                f"got warning={self.warning}, ready={self.ready}"
            )
        return self


class OperationConfig(MainModel):
    """Confirmed operation flags and token policy.

    Parse issues are always emitted: whenever a cell fails to parse, its issue
    code and its original text are written to ``_parse_issues``. Losing a value
    without a record of it is never a configurable outcome.

    ``full_raw_row`` is the one opt-in: it additionally preserves the original
    text of cells that parsed *successfully*, which duplicates the whole source
    dataset into the artifact.
    """

    null_tokens: tuple[str, ...]
    assign_indices: bool
    drop_empty_rows: bool
    full_raw_row: bool
    include_unique_ratio: bool
    include_per_column_parse_error_counts: bool
    approximate_unique: bool
    trace_mode: TraceMode
    decision_thresholds: DecisionThresholds

