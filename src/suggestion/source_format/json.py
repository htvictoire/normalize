"""Infer JsonSourceFormat (no file content needed)."""

from __future__ import annotations

from shared.models.operation import JsonSourceFormat


def infer_json_source_format() -> JsonSourceFormat:
    """Return a JsonSourceFormat — JSON has no format settings to infer."""
    return JsonSourceFormat()
