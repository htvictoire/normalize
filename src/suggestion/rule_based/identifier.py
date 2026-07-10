"""Rule-based identifier-column inference."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from shared.models.column import IdentifierColumnConfig

_TOKEN_SPLIT = re.compile(r"[^a-z0-9]+")
_ID_TOKEN_SET = frozenset({"id", "identifier", "uuid", "guid"})
_BUSINESS_KEY_TOKENS = frozenset({"key", "sku", "code", "number", "no"})
_UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_STRUCTURED_ID_PATTERN = re.compile(r"^[A-Za-z]+[-_][A-Za-z0-9][A-Za-z0-9_-]*$")
_MIN_IDENTIFIER_SAMPLE_COUNT = 3
_MIN_UNIQUE_RATIO = 0.95
_MIN_IDENTIFIER_CONFIDENCE = 0.75

IdentifierKind = Literal["primary", "foreign", "business_key", "opaque"]


@dataclass(frozen=True)
class IdentifierInference:
    config: IdentifierColumnConfig
    confidence: float


def _header_tokens(column_name: str) -> tuple[str, ...]:
    return tuple(token for token in _TOKEN_SPLIT.split(column_name.lower()) if token)


def _header_signal(column_name: str) -> tuple[float, IdentifierKind]:
    tokens = _header_tokens(column_name)
    normalized = "_".join(tokens)
    if not tokens:
        return 0.0, "opaque"
    if normalized in {"id", "record_id", "row_id", "uuid", "guid"}:
        return 1.0, "primary"
    if tokens[-1:] == ("id",) or tokens[-1:] == ("uuid",) or tokens[-1:] == ("guid",):
        return 0.9, "foreign"
    if any(token in _BUSINESS_KEY_TOKENS for token in tokens):
        return 0.75, "business_key"
    if any(token in _ID_TOKEN_SET for token in tokens):
        return 0.7, "opaque"
    return 0.0, "opaque"


def _shape_signal(values: list[str]) -> float:
    if not values:
        return 0.0
    uuid_count = sum(1 for value in values if _UUID_PATTERN.fullmatch(value))
    structured_count = sum(1 for value in values if _STRUCTURED_ID_PATTERN.fullmatch(value))
    fixed_length_count = max(
        (sum(1 for value in values if len(value) == length) for length in {len(v) for v in values}),
        default=0,
    )
    sample_count = len(values)
    return max(
        uuid_count / sample_count,
        structured_count / sample_count,
        fixed_length_count / sample_count * 0.6,
    )


def infer_identifier_type(column_name: str, values: list[str]) -> IdentifierInference | None:
    """Infer identifier config from header semantics and sampled uniqueness."""
    if len(values) < _MIN_IDENTIFIER_SAMPLE_COUNT:
        return None

    header_score, identifier_kind = _header_signal(column_name)
    if header_score <= 0:
        return None

    unique_ratio = len(set(values)) / len(values)
    if unique_ratio < _MIN_UNIQUE_RATIO:
        return None

    shape_score = _shape_signal(values)
    confidence = min(
        1.0,
        (header_score * 0.60) + (unique_ratio * 0.30) + (shape_score * 0.10),
    )
    if confidence < _MIN_IDENTIFIER_CONFIDENCE:
        return None

    return IdentifierInference(
        config=IdentifierColumnConfig(identifier_kind=identifier_kind),
        confidence=round(confidence, 4),
    )
