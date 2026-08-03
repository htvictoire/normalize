"""Runtime source-access contracts shared across app layers."""

from __future__ import annotations

from shared.models.base import MainModel
from shared.models.operation import FileFormat, FileSource


class SourceRef(MainModel):
    """Canonical source identity carried across lifecycle boundaries.

    ``source_file`` is absent for a draft source not yet at rest in storage —
    ``sample`` (base64-encoded raw bytes) stands in for it until a real location
    is attached. For CSV/JSON this is a raw prefix of the real file; for Excel
    it is a CSV conversion of a prefix instead, since .xlsx is a zip archive
    whose central directory sits at the end of the file — a truncated raw
    sample cannot be opened at all, so the caller converts before sending one.
    ``source_file_format`` still reports the real, eventually-uploaded format.
    """

    source_file: str | None = None
    source_type: FileSource
    source_file_name: str
    source_file_format: FileFormat
    sample: str | None = None


__all__ = ["SourceRef"]
