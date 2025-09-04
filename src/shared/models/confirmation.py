"""Confirmation-phase input model shared between app/ and downstream services."""

from __future__ import annotations

from shared.models.base import MainModel
from shared.models.column import ColumnConfig
from shared.models.operation import OperationConfig, SourceFormat


class ConfirmedConfig(MainModel):
    """User-confirmed configuration that drives all downstream phases."""

    source_format: SourceFormat
    column_config: dict[str, ColumnConfig]
    operation_config: OperationConfig
