"""Google Gemini inference provider."""

from __future__ import annotations

from typing import TypeVar

from shared.models.base import MainModel

from suggestion.ai.providers.base import FileInferenceProvider

T = TypeVar("T", bound=MainModel)


class GeminiInferenceProvider(FileInferenceProvider):
    """Structured-output inference backed by Google Gemini."""

    def infer_schema(self, sample_rows: str, prompt: str, output_model: type[T]) -> T:
        raise NotImplementedError("Gemini inference provider is not yet implemented.")
