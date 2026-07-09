"""Excel file-type inference for the AI strategy (stubbed — CSV lands first).

Excel infers a header location and per-column configs, but no delimiter (cells,
not delimited text). Sheet selection stays mechanical on our side.
"""

from __future__ import annotations

from shared.models.operation import HeaderMode
from shared.models.source import SourceRef

from suggestion.ai.formats.base import (
    AiColumnInference,
    AiInferenceResult,
    FormatInference,
    ReconciledInference,
)


class ExcelAiInferenceResult(AiInferenceResult):
    """Model output for an Excel source (no delimiter)."""

    header_mode: HeaderMode
    header_row_index: int | None
    header_confidence: float
    columns: list[AiColumnInference]


class ExcelFormatInference(FormatInference):
    """Excel prompt, sampling, and reconciliation."""

    output_model = ExcelAiInferenceResult

    def sample(self, source: SourceRef) -> str:
        raise NotImplementedError("Excel AI inference is not yet implemented.")

    def build_prompt(self, sample: str) -> str:
        raise NotImplementedError("Excel AI inference is not yet implemented.")

    def reconcile(self, result: AiInferenceResult, source: SourceRef) -> ReconciledInference:
        raise NotImplementedError("Excel AI inference is not yet implemented.")
