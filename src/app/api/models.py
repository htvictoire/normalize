"""HTTP request models for the normalization API endpoints."""

from __future__ import annotations

from pydantic import Field

from shared.models.instance_config import InstanceConfig
from shared.models.source import SourceRef


class SuggestRequest(SourceRef):
    """Request payload for the suggest endpoint."""

    source_checksum: str = Field(
        pattern="^[0-9a-f]{64}$",
        description="Lowercase hex-encoded SHA256 checksum (exactly 64 characters, no whitespace).",
    )


class ConfirmRequest(InstanceConfig):
    """Request payload for instance confirmation."""
