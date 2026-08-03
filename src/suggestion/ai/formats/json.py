"""JSON reading for the AI strategy.

JSON is self-describing — no delimiter, no header, no encoding to guess — so its
layout is declared rather than inferred and it reaches a reading without a model
call. Only its column types are inferred.
"""

from __future__ import annotations

from shared.models.operation import SourceFormat
from shared.models.source import SourceRef

from suggestion.ai.formats.base import DeclaredLayout
from suggestion.source import SourceReading, read_under_format
from suggestion.source.json import infer_json_source_format


class JsonFormatInference(DeclaredLayout):
    """JSON reading; the layout is fixed for every source of this type."""

    def source_format(self) -> SourceFormat:
        return infer_json_source_format()

    def read(self, source: SourceRef, source_format: SourceFormat) -> SourceReading:
        return read_under_format(source, source_format)
