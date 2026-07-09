"""Provider selection from settings — swap providers via NORMALIZE_AI_PROVIDER."""

from __future__ import annotations

from shared.settings import get_settings

from suggestion.ai.providers.base import FileInferenceProvider
from suggestion.ai.providers.claude import ClaudeInferenceProvider
from suggestion.ai.providers.gemini import GeminiInferenceProvider
from suggestion.ai.providers.openai import OpenAIInferenceProvider


def get_inference_provider() -> FileInferenceProvider:
    """Return the configured LLM inference provider."""
    provider = get_settings().ai_provider
    if provider == "claude":
        return ClaudeInferenceProvider()
    if provider == "openai":
        return OpenAIInferenceProvider()
    if provider == "gemini":
        return GeminiInferenceProvider()
    raise ValueError(f"Unsupported AI provider: {provider!r}")
