"""Per-file-type inference handlers, dispatched by source file format."""

from suggestion.ai.formats.base import FormatInference, ReconciledInference
from suggestion.ai.formats.registry import FORMATS

__all__ = [
    "FORMATS",
    "FormatInference",
    "ReconciledInference",
]
