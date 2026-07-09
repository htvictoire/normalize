"""Suggestion-phase output models."""

from __future__ import annotations

from pydantic import Field

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


class SuggestionConfidence(MainModel):
    """Per-inference confidence for a suggested config, mirroring what was guessed.

    Sibling of the suggested InstanceConfig, not nested inside it: InstanceConfig
    is reused as the user-authored confirmed_config, where confidence is meaningless.
    delimiter and header are optional because not every source format has them
    (Excel has no delimiter; JSON has neither). The rule-based strategy is
    deterministic and reports 1.0 for everything it infers.
    """

    delimiter: float | None = Field(default=None, ge=0.0, le=1.0)
    header: float | None = Field(default=None, ge=0.0, le=1.0)
    column_config: dict[str, float]  # keyed by position, one value per column


class SuggestionOutput(MainModel):
    """Full output of the suggestion pipeline."""

    suggested_config: InstanceConfig
    confidence: SuggestionConfidence
    display: SuggestionDisplay
    estimated_pipeline_seconds: int
