"""Backward-compatible exports for source format inference."""

from suggestion.source_format.infer import infer_source_format, infer_source_format_from_bytes

__all__ = ["infer_source_format", "infer_source_format_from_bytes"]
