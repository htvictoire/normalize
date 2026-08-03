"""Shared helpers for reading bytes from a source."""

from __future__ import annotations

import base64
from pathlib import Path

from shared.errors import SourceError
from shared.models.source import SourceRef
from shared.storage.s3 import fetch_s3_probe, s3_ref


def read_source_probe(source: SourceRef, n_bytes: int) -> bytes:
    """Return the first `n_bytes` of the original source.

    An absent or unreadable source raises ``SourceError``; other I/O failures
    propagate unchanged. A source carrying an inline ``sample`` is not yet at
    rest anywhere, so its bytes are decoded directly rather than fetched.
    """
    if n_bytes < 1:
        raise ValueError("n_bytes must be >= 1")

    if source.sample is not None:
        return base64.b64decode(source.sample)[:n_bytes]

    if source.source_file is None:
        raise SourceError("Source has neither an inline sample nor a source_file.")

    if source.source_type == "s3":
        return fetch_s3_probe(s3_ref(source.source_file), n_bytes)

    try:
        with Path(source.source_file).open("rb") as handle:
            return handle.read(n_bytes)
    except (FileNotFoundError, IsADirectoryError, NotADirectoryError) as exc:
        raise SourceError(f"Source file not found: {source.source_file!r}") from exc
