"""Provider abstraction — one LLM backend, agnostic to file type.

A provider is a generic structured-output executor: given a text sample, a
prompt, and a pydantic output model, it calls its LLM and returns an instance
of that model. It never knows CSV from JSON — the file-type-specific prompt and
output model are chosen by the reconciliation pipeline and passed in.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar

from shared.models.base import MainModel

T = TypeVar("T", bound=MainModel)


class FileInferenceProvider(ABC):
    """Base class for an LLM inference backend."""

    @abstractmethod
    def infer_schema(self, sample_rows: str, prompt: str, output_model: type[T]) -> T:
        """Call the LLM and return structured output validated as ``output_model``."""
        raise NotImplementedError
