"""Rule-based identifier-column inference."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from shared.models.column import (
    SUPPORTED_REASON_LOCALES,
    IdentifierColumnConfig,
    LocalizedReasons,
)

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
_SHAPE_MAJORITY_RATIO = 0.5

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


# Translation tables for the rule-based reasons. Each entry maps a locale to a
# format template; {placeholders} are filled with the column's own facts. Keys
# must cover every locale in SUPPORTED_REASON_LOCALES.
_NAME_REASON_TEMPLATES: dict[str, str] = {
    "en": "Column name '{name}' matches a primary-key naming convention.",
    "fr": "Le nom de colonne « {name} » suit une convention de clé primaire.",
    "es": "El nombre de columna «{name}» sigue una convención de clave primaria.",
    "ar": "اسم العمود '{name}' يطابق اصطلاح تسمية المفتاح الأساسي.",
}
_UNIQUENESS_REASON_TEMPLATES: dict[str, str] = {
    "en": "Sampled values are {pct} unique ({distinct} of {total} distinct).",
    "fr": "Les valeurs échantillonnées sont uniques à {pct} ({distinct} sur {total} distinctes).",
    "es": "Los valores muestreados son {pct} únicos ({distinct} de {total} distintos).",
    "ar": "القيم في العينة فريدة بنسبة {pct} ({distinct} من {total} مميزة).",
}
_SHAPE_REASON_TEMPLATES: dict[str, dict[str, str]] = {
    "uuid": {
        "en": "Values follow the canonical UUID/GUID format.",
        "fr": "Les valeurs suivent le format canonique UUID/GUID.",
        "es": "Los valores siguen el formato canónico UUID/GUID.",
        "ar": "تتبع القيم تنسيق UUID/GUID المعياري.",
    },
    "structured": {
        "en": "Values follow a structured, prefixed identifier pattern.",
        "fr": "Les valeurs suivent un motif d'identifiant structuré et préfixé.",
        "es": "Los valores siguen un patrón de identificador estructurado y con prefijo.",
        "ar": "تتبع القيم نمط معرّف منظم ومسبوق ببادئة.",
    },
    "fixed_length": {
        "en": "Values share a consistent fixed length of {length} characters.",
        "fr": "Les valeurs partagent une longueur fixe et constante de {length} caractères.",
        "es": "Los valores comparten una longitud fija y constante de {length} caracteres.",
        "ar": "تشترك القيم في طول ثابت ومتسق يبلغ {length} حرفًا.",
    },
    "opaque": {
        "en": "Values are opaque tokens that carry no meaning beyond row identity.",
        "fr": "Les valeurs sont des jetons opaques dont le seul sens est l'identité de ligne.",
        "es": "Los valores son tokens opacos sin significado más allá de la identidad de la fila.",
        "ar": "القيم رموز غير شفافة لا تحمل معنى يتجاوز هوية الصف.",
    },
}


def _shape_reason_key(values: list[str]) -> tuple[str, dict[str, object]]:
    """Classify the dominant value shape into a translation key and its params."""
    sample_count = len(values)
    uuid_ratio = sum(1 for value in values if _UUID_PATTERN.fullmatch(value)) / sample_count
    if uuid_ratio >= _SHAPE_MAJORITY_RATIO:
        return "uuid", {}
    structured_ratio = (
        sum(1 for value in values if _STRUCTURED_ID_PATTERN.fullmatch(value)) / sample_count
    )
    if structured_ratio >= _SHAPE_MAJORITY_RATIO:
        return "structured", {}
    lengths = {len(value) for value in values}
    if len(lengths) == 1:
        return "fixed_length", {"length": next(iter(lengths))}
    return "opaque", {}


def _primary_key_reasons(
    column_name: str, values: list[str], unique_ratio: float
) -> LocalizedReasons:
    """Build the three primary-key reasons in every supported locale."""
    distinct = len(set(values))
    pct = f"{unique_ratio:.0%}"
    shape_key, shape_params = _shape_reason_key(values)
    per_locale = {
        locale: (
            _NAME_REASON_TEMPLATES[locale].format(name=column_name),
            _UNIQUENESS_REASON_TEMPLATES[locale].format(
                pct=pct, distinct=distinct, total=len(values)
            ),
            _SHAPE_REASON_TEMPLATES[shape_key][locale].format(**shape_params),
        )
        for locale in SUPPORTED_REASON_LOCALES
    }
    return LocalizedReasons.model_validate(per_locale)


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

    reasons: LocalizedReasons | None = None
    if identifier_kind == "primary":
        reasons = _primary_key_reasons(column_name, values, unique_ratio)

    return IdentifierInference(
        config=IdentifierColumnConfig(identifier_kind=identifier_kind, reasons=reasons),
        confidence=round(confidence, 4),
    )
