"""Shared helpers for reading bytes from a source."""

from __future__ import annotations

from pathlib import Path

from shared.models.source import SourceRef
from shared.storage.s3 import fetch_s3_probe, s3_ref


def read_source_probe(source: SourceRef, n_bytes: int) -> bytes:
    """Return the first `n_bytes` of the original source."""
    if n_bytes < 1:
        raise ValueError("n_bytes must be >= 1")

    if source.source_type == "s3":
        return fetch_s3_probe(s3_ref(source.source_file), n_bytes)

    with Path(source.source_file).open("rb") as handle:
        return handle.read(n_bytes)
