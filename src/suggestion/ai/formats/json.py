"""JSON file-type inference for the AI strategy (stubbed — CSV lands first).

JSON is self-describing: no delimiter, no header, no encoding to guess. The
model's job is purely per-column typing.
"""

from __future__ import annotations

from shared.models.source import SourceRef

from suggestion.ai.formats.base import (
    AiColumnInference,
    AiInferenceResult,
    FormatInference,
    ReconciledInference,
)


class JsonAiInferenceResult(AiInferenceResult):
    """Model output for a JSON source (columns only)."""

    columns: list[AiColumnInference]


class JsonFormatInference(FormatInference):
    """JSON prompt, sampling, and reconciliation."""

    output_model = JsonAiInferenceResult

    def sample(self, source: SourceRef) -> str:
        raise NotImplementedError("JSON AI inference is not yet implemented.")

    def build_prompt(self, sample: str) -> str:
        raise NotImplementedError("JSON AI inference is not yet implemented.")

    def reconcile(self, result: AiInferenceResult, source: SourceRef) -> ReconciledInference:
        raise NotImplementedError("JSON AI inference is not yet implemented.")
