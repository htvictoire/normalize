"""Suggestion-phase output models."""

from __future__ import annotations

from pydantic import Field

from shared.models.base import MainModel
from shared.models.instance_config import InstanceConfig
from shared.models.issues import NormalizationIssue
from shared.models.operation import SuggestionMethod
from shared.models.profiling import ColumnCounts
from shared.models.source import SourceRef


class SuggestionInput(SourceRef):
    """Complete request metadata for one suggestion run."""

    source_checksum: str = Field(
        pattern="^[0-9a-f]{64}$",
        description=(
            "Lowercase hex-encoded SHA256 checksum (exactly 64 characters, no whitespace). "
            "Caller-attested and recorded for provenance; the engine does not re-read the "
            "source to verify it."
        ),
    )
    suggestion_method: SuggestionMethod
    extended_type_detection: bool
    webhook_url: str | None = None


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
    (Excel has no delimiter; JSON has neither).

    Only the AI strategy estimates these. The rule-based strategy reports a uniform
    RULE_BASED_CONFIDENCE for every inference because it does not score its guesses.
    """

    delimiter: float | None = Field(default=None, ge=0.0, le=1.0)
    header: float | None = Field(default=None, ge=0.0, le=1.0)
    column_config: dict[str, float]  # keyed by position, one value per column


class SuggestionOutput(MainModel):
    """Full output of the suggestion pipeline."""

    suggested_config: InstanceConfig
    confidence: SuggestionConfidence
    display: SuggestionDisplay
    issues: list[NormalizationIssue]
    estimated_pipeline_seconds: int
