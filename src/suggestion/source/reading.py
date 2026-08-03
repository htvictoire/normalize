"""The resolved-source-reading contract shared by every inference strategy."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

from shared.models.operation import FileFormat, FileSource, SourceFormat
from shared.models.source import SourceRef


def effective_file_format(source: SourceRef) -> FileFormat:
    """The format to actually read one source as.

    An excel-declared source carrying an inline sample holds a CSV conversion of
    a prefix, not raw XLSX bytes — .xlsx cannot be prefix-sampled at all (it is a
    zip archive whose central directory sits at the end of the file), so the
    caller converts a sample to CSV before sending it. The declared format stays
    "excel" — the file that eventually lands in storage is genuinely xlsx — only
    how *this* sample is read differs.
    """
    if source.source_file_format == "excel" and source.sample is not None:
        return "csv"
    return source.source_file_format


@dataclass(frozen=True)
class SourceReading:
    """Inferred format, raw sample rows, column names, inference rows, and ingestion target.

    Reading an S3 source leaves a temp file behind, so a reading is a context
    manager: leaving the block discards whatever it downloaded.
    """

    source_format: SourceFormat
    sample_rows: list[list[str]]
    column_names: list[str]
    inference_rows: list[list[str]]
    ingestion_source_url: str
    ingestion_source_type: FileSource
    cleanup_path: Path | None
    # Rows the parse could not position because their field count disagreed with
    # the header's. Only delimited formats can produce them.
    discarded_row_count: int = 0
    # Read from an inline sample rather than a real location: inference_rows is
    # everything there is, not a prefix of a larger file, so stats are computed
    # from it directly instead of a full-source DuckDB scan.
    is_sample_based: bool = False

    def __enter__(self) -> SourceReading:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.discard()

    def discard(self) -> None:
        """Remove any temp file this reading downloaded."""
        if self.cleanup_path is not None:
            self.cleanup_path.unlink(missing_ok=True)
