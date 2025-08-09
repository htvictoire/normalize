"""Suggestion-phase app service as a thin orchestrator."""

from __future__ import annotations

from pathlib import Path

from suggest.models import SuggestionOutput
from suggest.pipeline import run_suggestion


class SuggestionService:
    """Orchestrate suggestion pipeline for one source file."""

    def suggest(
        self,
        file_path: str | Path,
    ) -> SuggestionOutput:
        """Run suggestion pipeline and return inferred output."""
        return run_suggestion(file_path)


__all__ = ["SuggestionOutput", "SuggestionService"]
