"""SHA256 checksum resolution for local files and S3-compatible objects."""

from __future__ import annotations

import hashlib
from pathlib import Path

from shared.models.source import SourceRef
from shared.settings import get_settings
from shared.storage.s3 import S3ObjectRef, fetch_s3_checksum


def sha256_stream(path: Path, chunk_size: int = 1_048_576) -> str:
    """Compute SHA256 of a local file using chunked reads."""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def resolve_checksum(source: SourceRef) -> str:
    """
    Return the SHA256 checksum for a source file.

    For local files the checksum is computed by streaming the file.
    For S3-compatible objects the checksum is fetched from object metadata — no download.
    """
    if source.source_type == "s3":
        obj = S3ObjectRef(bucket=get_settings().s3_bucket, key=source.source_file)
        return fetch_s3_checksum(obj)
    return sha256_stream(Path(source.source_file))
