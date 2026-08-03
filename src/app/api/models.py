"""HTTP request models for the normalization API."""

from __future__ import annotations

from shared.models.base import MainModel
from shared.models.instance_config import InstanceConfig
from shared.models.suggestion import SuggestionInput


class SuggestRequest(SuggestionInput):
    """Request payload for the suggest and layout endpoints."""


class CreateConfirmedRequest(SuggestionInput):
    """Request payload for creating an instance from a caller-supplied config."""

    confirmed_config: InstanceConfig


class ConfirmRequest(MainModel):
    """Request payload for confirming an instance.

    ``source_file`` is required exactly when the instance is still a draft
    (created from a sample, with no source_file attached yet).
    """

    confirmed_config: InstanceConfig
    source_file: str | None = None
