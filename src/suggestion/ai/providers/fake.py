"""Deterministic inference provider for tests and pipeline-wiring validation.

Constructed with a canned result, it returns that result from infer_schema
regardless of inputs (validating only that the caller's output_model matches).
Not selectable via settings — injected directly into the pipeline by tests.
"""

from __future__ import annotations

from typing import TypeVar

from shared.models.base import MainModel

from suggestion.ai.providers.base import FileInferenceProvider

T = TypeVar("T", bound=MainModel)


class FakeInferenceProvider(FileInferenceProvider):
    """Returns a pre-built result, ignoring the prompt."""

    def __init__(self, result: MainModel) -> None:
        self._result = result

    def infer_schema(self, prompt: str, output_model: type[T]) -> T:  # noqa: ARG002 — canned result ignores the prompt
        if not isinstance(self._result, output_model):
            raise TypeError(
                f"FakeInferenceProvider was given a {type(self._result).__name__} "
                f"but the caller expected {output_model.__name__}."
            )
        return self._result
