"""Suggestion pipeline dispatcher — routes to the selected inference strategy."""

from __future__ import annotations

from shared.models.suggestion import SuggestionInput, SuggestionOutput

from suggestion.ai.pipeline import run_suggestion as run_ai_suggestion
from suggestion.rule_based.pipeline import run_suggestion as run_rule_based_suggestion


def run_suggestion(request: SuggestionInput) -> SuggestionOutput:
    """Run the suggestion pipeline for one source file using the selected strategy."""
    if request.suggestion_method == "rule_based":
        return run_rule_based_suggestion(
            request,
        )
    if request.suggestion_method == "ai":
        return run_ai_suggestion(
            request,
        )
    raise ValueError(f"Unsupported suggestion method: {request.suggestion_method!r}")
