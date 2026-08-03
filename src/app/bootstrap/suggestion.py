"""Suggestion-phase app service."""

from __future__ import annotations

from shared.models.suggestion import LayoutOutput, SuggestionInput, TypingOutput

from suggestion import run_layout, run_suggestion, run_typing


class SuggestionService:
    def suggest(self, request: SuggestionInput) -> tuple[LayoutOutput, TypingOutput]:
        return run_suggestion(request)

    def resolve_layout(self, request: SuggestionInput) -> LayoutOutput:
        return run_layout(request)

    def type_columns(self, request: SuggestionInput, layout: LayoutOutput) -> TypingOutput:
        return run_typing(request, layout)


__all__ = ["SuggestionService"]
