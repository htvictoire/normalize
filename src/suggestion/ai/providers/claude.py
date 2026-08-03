"""Anthropic Claude inference provider.

The reply is constrained by the API to the output model's JSON Schema, so an
off-schema answer is not a case this provider handles: no schema in the prompt,
no corrective re-prompt loop. Two adjustments make a pydantic schema acceptable
to that enforcement, both re-applied when the reply is validated:

  - a discriminated union serializes as ``oneOf`` + ``discriminator``, of which
    only ``anyOf`` is accepted;
  - numeric and length bounds are rejected outright.

Transport failures are retried by the SDK. A reply that clears the schema but
fails validation is a genuine model error and is raised rather than retried;
the phase that called it is already retried by its own caller.
"""

from __future__ import annotations

from typing import Any, TypeVar

import anthropic
from pydantic import ValidationError

from shared.errors import (
    InferenceValidationError,
    ProviderQuotaExceededError,
    ProviderUnreachableError,
)
from shared.models.base import MainModel
from shared.settings import get_settings

from suggestion.ai.providers.base import FileInferenceProvider

T = TypeVar("T", bound=MainModel)

# Wide sources type more columns; sized above the widest observed answer and below
# the point where a non-streaming request risks an HTTP timeout.
_MAX_TOKENS = 8192

# Keywords the structured-output schema subset rejects. Each is re-applied when
# the reply is validated against the pydantic model.
_UNSUPPORTED_KEYWORDS = frozenset(
    {
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
        "uniqueItems",
    }
)


def _enforceable(node: Any) -> Any:
    """Return the schema with rejected keywords dropped and unions as anyOf."""
    if isinstance(node, dict):
        adapted = {
            key: _enforceable(value)
            for key, value in node.items()
            if key != "discriminator" and key not in _UNSUPPORTED_KEYWORDS
        }
        if "oneOf" in adapted:
            adapted["anyOf"] = adapted.pop("oneOf")
        return adapted
    if isinstance(node, list):
        return [_enforceable(item) for item in node]
    return node


class ClaudeInferenceProvider(FileInferenceProvider):
    """Structured-output inference backed by Anthropic Claude."""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.claude_api_key:
            raise RuntimeError("NORMALIZE_CLAUDE_API_KEY is not set.")
        self._client = anthropic.Anthropic(api_key=settings.claude_api_key)
        self._model = settings.claude_model
        self._schemas: dict[type[MainModel], Any] = {}

    def infer_schema(self, prompt: str, output_model: type[T]) -> T:
        schema = self._schemas.setdefault(
            output_model, _enforceable(output_model.model_json_schema())
        )
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=_MAX_TOKENS,
                # Thinking runs adaptive by default and terminates once the schema-constrained
                # array reaches a validly-closeable state, which can be well short of one entry
                # per input row; disabling it keeps generation in the same pass as enforcement.
                thinking={"type": "disabled"},
                messages=[{"role": "user", "content": prompt}],
                output_config={"format": {"type": "json_schema", "schema": schema}},
            )
        except anthropic.RateLimitError as exc:
            raise ProviderQuotaExceededError(
                "The AI service quota has been exhausted. Retry after the quota "
                "window resets, or raise the provider plan limit."
            ) from exc
        except (anthropic.APIConnectionError, anthropic.InternalServerError) as exc:
            raise ProviderUnreachableError(
                "The AI service is currently unavailable. Please try again shortly."
            ) from exc

        reply = "".join(block.text for block in response.content if block.type == "text")
        try:
            return output_model.model_validate_json(reply)
        except ValidationError as exc:
            raise InferenceValidationError(
                f"The AI returned a {output_model.__name__} that failed validation."
            ) from exc
