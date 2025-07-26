"""HTTP request models for normalization API endpoints."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from shared.models.base import MainModel
from shared.models.column import ColumnConfig
from shared.models.operation import OperationConfig, RunMode


class SuggestRequest(MainModel):
    """Request payload for suggest endpoint."""

    name: str = Field(min_length=1)
    file: str = Field(min_length=1)


class ConfirmRequest(MainModel):
    """Request payload for instance confirmation."""

    confirmed_column_config: dict[str, ColumnConfig]
    operation_config: OperationConfig


class NormalizeRequest(MainModel):
    """Request payload to trigger normalization."""

    output_dir: Path = Path("data/manual_runs")
    mode: RunMode
    rules_version: str = "v1"
