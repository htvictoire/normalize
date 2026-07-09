"""Per-file-type inference contracts for the AI strategy.

Everything that varies by file type — the LLM output schema, the prompt, how
the raw sample is built, and how the model's answer is reconciled into a
resolved source_format + column_config — lives behind FormatInference. The
pipeline dispatches by source_file_format and is otherwise format-blind.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from shared.models.base import MainModel
from shared.models.column import ColumnConfig
from shared.models.source import SourceRef
from shared.models.suggestion import SuggestionConfidence

from suggestion.source import SourceReading


class AiInferenceResult(MainModel):
    """Marker base for a provider's structured output. Shape varies per file type."""


class AiColumnInference(MainModel):
    """One column as inferred by the model: its config and how sure the model is."""

    name: str
    config: ColumnConfig
    confidence: float


@dataclass(frozen=True)
class ReconciledInference:
    """An AI result mapped into the ingredients the shared assembler needs.

    ``reading`` carries the AI-resolved source_format plus the rows re-parsed
    under it (for the full-source stats scan and display), so the rest of the
    pipeline is identical to the rule-based path from here on.
    """

    reading: SourceReading
    column_config: dict[str, ColumnConfig]  # keyed by position
    confidence: SuggestionConfidence


class FormatInference(ABC):
    """What every file type must supply to the AI pipeline."""

    output_model: type[AiInferenceResult]

    @abstractmethod
    def sample(self, source: SourceRef) -> str:
        """Build the raw text sample handed to the model (no structure pre-applied)."""
        raise NotImplementedError

    @abstractmethod
    def build_prompt(self, sample: str) -> str:
        """Build the file-type-specific prompt around the sample."""
        raise NotImplementedError

    @abstractmethod
    def reconcile(self, result: AiInferenceResult, source: SourceRef) -> ReconciledInference:
        """Map the model's answer into a resolved reading + column_config + confidence."""
        raise NotImplementedError
