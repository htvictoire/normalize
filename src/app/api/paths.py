"""Path helpers for API request handling."""

from __future__ import annotations

from pathlib import Path


def resolve_data_file(file_name: str) -> Path:
    """Resolve an API payload file reference to a local source path."""
    candidate = Path(file_name)
    if candidate.is_absolute():
        return candidate
    if candidate.exists():
        return candidate
    return Path("data") / candidate
