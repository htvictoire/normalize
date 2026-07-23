"""Google Gemini inference provider.

We force JSON output, embed the JSON Schema in the prompt, and validate the reply
client-side with pydantic, retrying on failure.

We deliberately do NOT use Gemini's native ``response_schema`` enforcement. It is
technically possible (after adapting the schema to Gemini's subset), but it
regresses type-detection quality badly: the model loses effective access to our
field descriptions — the "classify as X when Y" guidance those descriptions carry
— and an enforced ``anyOf`` biases it toward the trivially-valid ``string``
branch. Measured on this workload, native enforcement made the model type nearly
every column as ``string``, while the embedded schema (descriptions visible in the
prompt as reasoning material) typed them correctly. Enforcement is also
unnecessary: the output models are kept simple enough — no free-form maps, no
jargon enums — that the model reliably returns valid JSON, and the retry covers
the rare miss.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, TypeVar

from pydantic import ValidationError

from shared.errors import (
    InferenceValidationError,
    ProviderQuotaExceededError,
    ProviderUnreachableError,
)
from shared.models.base import MainModel
from shared.settings import get_settings

from suggestion.ai.providers.base import FileInferenceProvider

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=MainModel)

_MAX_ATTEMPTS = 3
# Retries reuse the same prompt, so at temperature 0 they'd regenerate the same
# reply. A small non-zero temperature perturbs the retry enough to break out of a
# stuck output while keeping the first (best-quality) attempt greedy.
_RETRY_TEMPERATURE = 0.3
_BASE_BACKOFF_SECONDS = 0.5
_MAX_BACKOFF_SECONDS = 2.0
_HTTP_TOO_MANY_REQUESTS = 429

# Optional dependency (the "ai" extra). Held as Any so this module type-checks
# whether or not google-genai is installed in the current environment.
_genai: Any = None
_genai_types: Any = None
# Provider HTTP-status errors and transport failures, treated as "unreachable".
_UNREACHABLE_ERRORS: tuple[type[BaseException], ...] = ()
try:
    import google.genai
    import google.genai.errors
    import google.genai.types
    import httpx
except ImportError:  # pragma: no cover - exercised when dependency is missing at runtime
    pass
else:
    _genai = google.genai
    _genai_types = google.genai.types
    _UNREACHABLE_ERRORS = (google.genai.errors.APIError, httpx.HTTPError)


def _backoff_seconds(attempt: int) -> float:
    """Capped exponential backoff."""
    delay: float = _BASE_BACKOFF_SECONDS * (2**attempt)
    return min(_MAX_BACKOFF_SECONDS, delay)


def _is_quota_exhausted(exc: BaseException) -> bool:
    """Whether a provider error is an HTTP 429 quota / rate-limit rejection."""
    if _genai is None or not isinstance(exc, _genai.errors.APIError):
        return False
    return (
        getattr(exc, "code", None) == _HTTP_TOO_MANY_REQUESTS
        or getattr(exc, "status", None) == "RESOURCE_EXHAUSTED"
    )


class GeminiInferenceProvider(FileInferenceProvider):
    """Structured-output inference backed by Google Gemini."""

    def infer_schema(self, prompt: str, output_model: type[T]) -> T:
        if _genai is None:
            raise RuntimeError(
                "google-genai is required for the Gemini provider. "
                "Install it with: pip install -e '.[ai]'"
            )
        settings = get_settings()
        if not settings.gemini_api_key:
            raise RuntimeError("NORMALIZE_GEMINI_API_KEY is not set.")

        client = _genai.Client(api_key=settings.gemini_api_key)
        base_contents = (
            f"{prompt}\n\n"
            "Respond with ONLY a JSON object — no prose, no code fences — matching "
            f"this JSON Schema:\n{json.dumps(output_model.model_json_schema())}"
        )

        contents = base_contents
        last_error: BaseException | None = None
        last_unreachable = False
        for attempt in range(_MAX_ATTEMPTS):
            if attempt:
                time.sleep(_backoff_seconds(attempt))
            config = _genai_types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0 if attempt == 0 else _RETRY_TEMPERATURE,
                # Column typing is pattern recognition, not multi-step reasoning, so model
                # "thinking" adds latency + tokens for no quality gain (measured: +42s and
                # +12k tokens on a thinking model, marginal result change). Disable it;
                # non-thinking models ignore this.
                thinking_config=_genai_types.ThinkingConfig(thinking_budget=0),
            )
            try:
                response = client.models.generate_content(
                    model=settings.gemini_model,
                    contents=contents,
                    config=config,
                )
            except _UNREACHABLE_ERRORS as exc:
                # Quota/rate-limit rejections do not recover within the window, and each
                # retry consumes more of the same allowance: fail fast without retrying.
                if _is_quota_exhausted(exc):
                    logger.exception("Gemini quota exhausted")
                    raise ProviderQuotaExceededError(
                        "The AI service quota has been exhausted. Retry after the quota "
                        "window resets, or raise the provider plan limit."
                    ) from exc
                last_error, last_unreachable = exc, True
                continue
            raw = response.text or ""
            try:
                return output_model.model_validate_json(raw)
            except ValidationError as exc:
                last_error, last_unreachable = exc, False
                # Show the model its own broken output and the error so the next
                # attempt can correct it, rather than blindly regenerating.
                contents = (
                    f"{base_contents}\n\n"
                    "Your previous response was not valid for the schema:\n"
                    f"{raw}\n\n"
                    f"It failed with:\n{exc}\n\n"
                    "Return a corrected JSON object that fixes every error above. "
                    "Emit only valid JSON — escape quotes and special characters "
                    "inside string values."
                )

        if last_unreachable:
            logger.error(
                "Gemini unreachable after %d attempts", _MAX_ATTEMPTS, exc_info=last_error
            )
            raise ProviderUnreachableError(
                "The AI service is currently unavailable. Please try again shortly."
            ) from last_error
        raise InferenceValidationError(
            f"The AI did not return a valid {output_model.__name__} after "
            f"{_MAX_ATTEMPTS} attempts."
        ) from last_error
