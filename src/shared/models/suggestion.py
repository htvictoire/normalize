"""Suggestion-phase output model shared between the suggestion pipeline and app layers."""

from __future__ import annotations

from pydantic import Field

from shared.models.base import MainModel
from shared.models.column import ColumnConfig
from shared.models.operation import SourceFormat
from shared.models.profiling import ColumnCounts


class SuggestedColumn(MainModel):
    """Per-column suggestion: label, inferred config, counts, and sample values."""

    label: str
    config: ColumnConfig
    counts: ColumnCounts
    sample_values: list[str] = Field(default_factory=list)


class SuggestionOutput(MainModel):
    """Suggestion-phase output. Provisional — all fields depend on inferred source format."""

    source_format: SourceFormat
    null_tokens: tuple[str, ...]
    row_count: int
    columns: dict[str, SuggestedColumn]
    sample_rows: list[list[str]] = Field(default_factory=list)
