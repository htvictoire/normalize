"""Configuration override helpers with source-format field protection."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

SOURCE_FORMAT_FIELDS = frozenset(
    {
        "encoding",
        "delimiter",
        "header_mode",
        "header_row_index",
        "decimal_separator",
        "thousand_separator",
        "allow_leading_decimal_point",
        "date_formats",
    }
)


def apply_override_layers(
    base_config: Mapping[str, Any],
    *,
    rules: Mapping[str, Any] | None = None,
    template: Mapping[str, Any] | None = None,
    workspace: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Merge override layers while enforcing caller-only source-format fields.

    Precedence order:
    1. base_config
    2. rules
    3. template
    4. workspace
    """
    merged: dict[str, Any] = dict(base_config)
    for layer_name, layer in (
        ("rules", rules),
        ("template", template),
        ("workspace", workspace),
    ):
        if layer is None:
            continue
        reject_override_exempt_fields(layer, layer_name=layer_name)
        merged.update(layer)
    return merged


def reject_override_exempt_fields(layer: Mapping[str, Any], *, layer_name: str) -> None:
    """Raise if an override layer attempts to mutate source-format config."""
    forbidden = sorted(field for field in layer if field in SOURCE_FORMAT_FIELDS)
    if forbidden:
        fields = ", ".join(forbidden)
        raise ValueError(
            f"{layer_name} override cannot set source-format fields: {fields}"
        )
