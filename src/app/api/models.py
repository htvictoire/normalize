"""HTTP request models for the normalization API endpoints."""

from __future__ import annotations

from shared.models.confirmation import ConfirmedConfig
from shared.models.source import SourceRef


class SuggestRequest(SourceRef):
    """Request payload for the suggest endpoint."""


class ConfirmRequest(ConfirmedConfig):
    """Request payload for instance confirmation."""
