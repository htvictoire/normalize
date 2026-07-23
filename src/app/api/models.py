"""HTTP request models for the normalization API."""

from __future__ import annotations

from shared.models.suggestion import SuggestionInput


class SuggestRequest(SuggestionInput):
    """Request payload for the suggest endpoint."""
