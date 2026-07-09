"""OpenAI GPT inference provider."""

from __future__ import annotations

from typing import TypeVar

from shared.models.base import MainModel

from suggestion.ai.providers.base import FileInferenceProvider

T = TypeVar("T", bound=MainModel)


class OpenAIInferenceProvider(FileInferenceProvider):
    """Structured-output inference backed by OpenAI GPT."""

    def infer_schema(self, sample_rows: str, prompt: str, output_model: type[T]) -> T:
        raise NotImplementedError("OpenAI inference provider is not yet implemented.")
