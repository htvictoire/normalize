"""
Checksum helpers for ingestion.

This module provides streaming SHA256 computation (no full-file in-memory read).
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_stream(path: Path, chunk_size: int = 1_048_576) -> str:
    """
    Compute SHA256 using chunked reads.

    Args:
    - `path`: file to hash.
    - `chunk_size`: bytes read per iteration.

    Returns:
    - lowercase hexadecimal SHA256 digest.
    """
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()
