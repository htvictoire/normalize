"""HTTP request models for the normalization API endpoints."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from shared.models.base import MainModel
from shared.models.confirmation import ConfirmedConfig
from shared.models.operation import RunMode


class SuggestRequest(MainModel):
    """Request payload for the suggest endpoint."""

    name: str = Field(min_length=1)
    file: str = Field(min_length=1)


class ConfirmRequest(ConfirmedConfig):
    """Request payload for instance confirmation."""


class NormalizeRequest(MainModel):
    """Request payload to trigger normalization."""

    output_dir: Path = Path("data/manual_runs")
    mode: RunMode
    rules_version: str = "v1"
