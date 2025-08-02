"""Column-config position-to-canonical resolution."""

from __future__ import annotations

from collections.abc import Mapping

from shared.models.column import ColumnConfig
from shared.utils.column_positions import build_position_to_name


def resolve_column_config_by_canonical(
    *,
    data_columns: list[str],
    column_config: dict[str, ColumnConfig] | Mapping[str, ColumnConfig],
) -> dict[str, ColumnConfig]:
    """Resolve position-keyed column config entries to canonical column names."""
    position_to_name = build_position_to_name(data_columns)
    return {position_to_name[position_key]: spec for position_key, spec in column_config.items()}
