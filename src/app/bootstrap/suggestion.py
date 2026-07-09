"""Suggestion-phase app service."""

from __future__ import annotations

from shared.models.operation import SuggestionMethod
from shared.models.source import SourceRef
from shared.models.suggestion import SuggestionOutput

from suggestion import run_suggestion


class SuggestionService:
    def suggest(self, source: SourceRef, method: SuggestionMethod) -> SuggestionOutput:
        return run_suggestion(source, method)


__all__ = ["SuggestionService"]
