"""Instance configuration model shared across suggestion, confirmation, and profiling."""

from __future__ import annotations

from shared.models.base import MainModel
from shared.models.column import ColumnConfig
from shared.models.operation import OperationConfig, SourceFormat


class InstanceConfig(MainModel):
    """Full configuration for one normalization instance."""

    source_format: SourceFormat
    column_config: dict[str, ColumnConfig]
    operation_config: OperationConfig
