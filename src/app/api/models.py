"""HTTP request models for the normalization API endpoints."""

from __future__ import annotations

from shared.models.base import MainModel
from shared.models.instance_config import InstanceConfig
from shared.models.suggestion import SuggestionInput


class SuggestRequest(SuggestionInput):
    """Request payload for the suggest endpoint."""


class ConfirmRequest(MainModel):
    """Request payload for instance confirmation."""

    config: InstanceConfig
    proceed_with_pipeline: bool = False
    webhook_url: str | None = None
