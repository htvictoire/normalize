"""File-format dispatch table for AI inference handlers."""

from __future__ import annotations

from shared.models.operation import FileFormat

from suggestion.ai.formats.base import FormatInference
from suggestion.ai.formats.csv import CsvFormatInference
from suggestion.ai.formats.excel import ExcelFormatInference
from suggestion.ai.formats.json import JsonFormatInference

FORMATS: dict[FileFormat, FormatInference] = {
    "csv": CsvFormatInference(),
    "excel": ExcelFormatInference(),
    "json": JsonFormatInference(),
}
