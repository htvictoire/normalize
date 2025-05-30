"""Checksum helpers for artifact files and manifest payloads."""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file(path: str | Path, *, chunk_size: int = 1_048_576) -> str:
    """Compute SHA256 hex digest for a file using chunked reads."""
    file_path = Path(path)
    hasher = hashlib.sha256()
    with file_path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Compute SHA256 hex digest for bytes payload."""
    return hashlib.sha256(data).hexdigest()
