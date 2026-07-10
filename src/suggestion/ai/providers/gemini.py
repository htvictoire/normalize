"""Google Gemini inference provider.

Gemini's native ``response_schema`` rejects several shapes our output models
rely on — discriminated unions (googleapis/python-genai#652), unions
(#861), and fields with default values (#699), and every ColumnConfig variant
has a defaulted ``type`` discriminator. So instead of native schema
enforcement we force JSON output, embed the JSON Schema in the prompt, and
validate the reply client-side with pydantic, retrying on validation failure.
"""

from __future__ import annotations

import json
from typing import Any, TypeVar

from pydantic import ValidationError

from shared.models.base import MainModel
from shared.settings import get_settings

from suggestion.ai.providers.base import FileInferenceProvider

T = TypeVar("T", bound=MainModel)

_MAX_ATTEMPTS = 3

# Optional dependency (the "ai" extra). Held as Any so this module type-checks
# whether or not google-genai is installed in the current environment.
_genai: Any = None
_genai_types: Any = None
try:
    import google.genai
    import google.genai.types
except ImportError:  # pragma: no cover - exercised when dependency is missing at runtime
    pass
else:
    _genai = google.genai
    _genai_types = google.genai.types


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
        contents = (
            f"{prompt}\n\n"
            "Respond with ONLY a JSON object — no prose, no code fences — matching "
            f"this JSON Schema:\n{json.dumps(output_model.model_json_schema())}"
        )
        config = _genai_types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.0,
            # Column typing is pattern recognition, not multi-step reasoning, so model
            # "thinking" adds latency + tokens for no quality gain (measured: +42s and
            # +12k tokens on a thinking model, marginal result change). Disable it;
            # non-thinking models ignore this.
            thinking_config=_genai_types.ThinkingConfig(thinking_budget=0),
        )

        last_error: ValidationError | None = None
        for _ in range(_MAX_ATTEMPTS):
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=contents,
                config=config,
            )
            try:
                return output_model.model_validate_json(response.text or "")
            except ValidationError as exc:
                last_error = exc
        raise RuntimeError(
            f"Gemini did not return valid {output_model.__name__} JSON after "
            f"{_MAX_ATTEMPTS} attempts: {last_error}"
        )
