"""Runtime source-access contracts shared across app layers."""

from __future__ import annotations

from shared.models.base import MainModel
from shared.models.operation import FileFormat, FileSource


class SourceRef(MainModel):
    """Canonical source identity carried across lifecycle boundaries."""

    source_file: str
    source_type: FileSource
    source_file_name: str
    source_file_format: FileFormat


__all__ = ["SourceRef"]
