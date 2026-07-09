"""Suggestion pipeline dispatcher — routes to the selected inference strategy."""

from __future__ import annotations

from shared.models.operation import SuggestionMethod
from shared.models.source import SourceRef
from shared.models.suggestion import SuggestionOutput

from suggestion.rule_based.pipeline import run_suggestion as run_rule_based_suggestion


def run_suggestion(source: SourceRef, method: SuggestionMethod) -> SuggestionOutput:
    """Run the suggestion pipeline for one source file using the selected strategy."""
    if method == "rule_based":
        return run_rule_based_suggestion(source)
    if method == "ai":
        raise NotImplementedError("The 'ai' suggestion method is not yet implemented.")
    raise ValueError(f"Unsupported suggestion method: {method!r}")
