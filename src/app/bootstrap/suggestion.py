"""Suggestion-phase app service."""

from __future__ import annotations

from shared.models.suggestion import SuggestionInput, SuggestionOutput

from suggestion import run_suggestion


class SuggestionService:
    def suggest(self, request: SuggestionInput) -> SuggestionOutput:
        return run_suggestion(request)


__all__ = ["SuggestionService"]
