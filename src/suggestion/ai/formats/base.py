"""Per-file-type inference contracts for the AI strategy.

Everything that varies by file type — the LLM output schema, the prompt, how
the raw sample is built, and how the model's answer is reconciled into a
resolved source_format + column_config — lives behind FormatInference. The
pipeline dispatches by source_file_format and is otherwise format-blind.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

from pydantic import Field, create_model

from shared.db.column_index import build_position_to_name
from shared.errors import SourceError
from shared.models.base import MainModel
from shared.models.column import ColumnConfig, CoreColumnConfig
from shared.models.source import SourceRef
from shared.models.suggestion import SuggestionConfidence

from suggestion.source import SourceReading


class AiInferenceResult(MainModel):
    """Marker base for a provider's structured output. Shape varies per file type."""


class AiColumnInference(MainModel):
    """One extended-mode column inferred by the model.

    This schema includes every executable ColumnConfig, including AI-only configs
    such as categorical, email, URL, IP address, and phone.
    """

    name: str
    config: ColumnConfig
    confidence: float = Field(
        ge=0.0, le=1.0, description="How sure the inferred type and config are."
    )


class CoreAiColumnInference(MainModel):
    """AI column inference constrained to core non-extended column configs."""

    name: str
    config: CoreColumnConfig
    confidence: float = Field(
        ge=0.0, le=1.0, description="How sure the inferred type and config are."
    )


type AnyAiColumnInference = AiColumnInference | CoreAiColumnInference


def make_core_output_model(
    name: str,
    base_model: type[AiInferenceResult],
) -> type[AiInferenceResult]:
    """Derive a core-mode output model by replacing only the column config schema."""
    return cast(
        type[AiInferenceResult],
        create_model(
            name,
            __base__=base_model,
            columns=(list[CoreAiColumnInference], ...),
        ),
    )


def pair_columns_by_position(
    column_names: list[str],
    ai_columns: Sequence[AnyAiColumnInference],
) -> tuple[dict[str, ColumnConfig], dict[str, float]]:
    """Key the model's ordered columns to positions (one AI column per parsed column).

    For positional formats (CSV, Excel), where the model returns columns
    left-to-right. Returns (column_config, confidences), both keyed by position.
    Raises if the model's column count disagrees with the parsed column count.
    """
    positions = list(build_position_to_name(column_names).keys())
    if not positions:
        raise SourceError("The source parsed into no columns.")
    if len(ai_columns) != len(positions):
        raise ValueError(
            f"Model returned {len(ai_columns)} columns but the source parsed into "
            f"{len(positions)}."
        )
    paired = list(zip(positions, ai_columns, strict=True))
    return (
        {pos: col.config for pos, col in paired},
        {pos: col.confidence for pos, col in paired},
    )


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
    core_output_model: type[AiInferenceResult] | None = None

    def output_model_for_options(
        self,
        extended_type_detection: bool,
    ) -> type[AiInferenceResult]:
        """Return the structured output model for the selected suggestion options."""
        if not extended_type_detection and self.core_output_model is not None:
            return self.core_output_model
        return self.output_model

    def validate_result_type(self, result: AiInferenceResult) -> None:
        """Validate that a provider result matches this format's possible output models."""
        valid_types = (
            (self.output_model,)
            if self.core_output_model is None
            else (self.output_model, self.core_output_model)
        )
        if not isinstance(result, valid_types):
            expected = " or ".join(model.__name__ for model in valid_types)
            raise TypeError(
                f"{type(self).__name__} expected {expected}, got {type(result).__name__}."
            )

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
