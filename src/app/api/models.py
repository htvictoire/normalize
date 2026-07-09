"""HTTP request models for the normalization API endpoints."""

from __future__ import annotations

from pydantic import Field

from shared.models.base import MainModel
from shared.models.instance_config import InstanceConfig
from shared.models.operation import SuggestionMethod
from shared.models.source import SourceRef


class SuggestRequest(SourceRef):
    """Request payload for the suggest endpoint."""

    source_checksum: str = Field(
        pattern="^[0-9a-f]{64}$",
        description="Lowercase hex-encoded SHA256 checksum (exactly 64 characters, no whitespace).",
    )
    suggestion_method: SuggestionMethod = "rule_based"


class ConfirmRequest(MainModel):
    """Request payload for instance confirmation."""

    config: InstanceConfig
    proceed_with_pipeline: bool = False
    webhook_url: str | None = None
