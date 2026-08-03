"""Suggestion-phase output models."""

from __future__ import annotations

from pydantic import Field, model_validator

from shared.models.base import MainModel
from shared.models.column import ColumnConfig
from shared.models.issues import NormalizationIssue
from shared.models.operation import InferenceMethod, OperationConfig, SourceFormat
from shared.models.profiling import ColumnCounts
from shared.models.source import SourceRef


class SuggestionInput(SourceRef):
    """Complete request metadata for one suggestion run.

    ``source_file`` may be absent only for a draft source identified by
    ``sample`` alone; the instance stays a draft (``InstanceModel.is_draft``)
    until a real location is attached at confirmation. For ``source_file_format
    == "excel"``, ``sample`` holds a CSV conversion of a prefix rather than raw
    XLSX bytes — .xlsx cannot be prefix-sampled at all (its central directory
    sits at the end of the file), so the caller converts before sending one.
    """

    source_checksum: str = Field(
        pattern="^[0-9a-f]{64}$",
        description=(
            "Lowercase hex-encoded SHA256 checksum (exactly 64 characters, no whitespace). "
            "Caller-attested and recorded for provenance; the engine does not re-read the "
            "source to verify it. Computable from local bytes before an upload finishes, "
            "so unlike source_file it is never deferred."
        ),
    )
    layout_method: InferenceMethod
    typing_method: InferenceMethod
    extended_type_detection: bool
    webhook_url: str | None = None

    @model_validator(mode="after")
    def _has_a_source(self) -> SuggestionInput:
        """Reject a request with neither a real location nor an inline sample."""
        if self.source_file is None and self.sample is None:
            raise ValueError("Either source_file or sample is required.")
        return self


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


class LayoutConfidence(MainModel):
    """Confidence in each layout decision made for a source.

    Both are optional because not every source format has them (Excel has no
    delimiter; JSON has neither).
    """

    delimiter: float | None = Field(default=None, ge=0.0, le=1.0)
    header: float | None = Field(default=None, ge=0.0, le=1.0)


class LayoutOutput(MainModel):
    """What resolving and parsing a source's layout yields, before anything is typed.

    Carries the parts of an InstanceConfig the layout determines. Confidence is
    only estimated by the AI strategy; the rule-based strategy reports a uniform
    RULE_BASED_CONFIDENCE because it does not score its guesses.
    """

    source_format: SourceFormat
    operation_config: OperationConfig
    display: SuggestionDisplay
    confidence: LayoutConfidence
    estimated_pipeline_seconds: int


class TypingOutput(MainModel):
    """What typing a parsed source's columns yields.

    Both maps are keyed by column position, one entry per column.
    """

    column_config: dict[str, ColumnConfig]
    confidence: dict[str, float]
    issues: list[NormalizationIssue]
