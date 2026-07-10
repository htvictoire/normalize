"""Anthropic Claude inference provider."""

from __future__ import annotations

from typing import TypeVar

from shared.models.base import MainModel

from suggestion.ai.providers.base import FileInferenceProvider

T = TypeVar("T", bound=MainModel)


class ClaudeInferenceProvider(FileInferenceProvider):
    """Structured-output inference backed by Anthropic Claude."""

    def infer_schema(self, prompt: str, output_model: type[T]) -> T:
        raise NotImplementedError("Claude inference provider is not yet implemented.")
