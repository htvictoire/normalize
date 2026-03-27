"""Suggestion-phase output models."""

from __future__ import annotations

from shared.models.base import MainModel
from shared.models.instance_config import InstanceConfig
from shared.models.profiling import ColumnCounts


class SuggestedColumnDisplay(MainModel):
    """Display data for one column produced during suggestion."""

    label: str
    counts: ColumnCounts
    sample_values: list[str]


class SuggestionDisplay(MainModel):
    """Display-only output from the suggestion phase. Never read by any pipeline stage."""

    row_count: int
    columns: dict[str, SuggestedColumnDisplay]  # keyed by position
    sample_rows: list[list[str]]


class SuggestionOutput(MainModel):
    """Full output of the suggestion pipeline."""

    suggested_config: InstanceConfig
    display: SuggestionDisplay
