"""Basic type inference stage."""

from __future__ import annotations

from collections.abc import Mapping
from time import perf_counter

from duckdb import DuckDBPyConnection

from normalize.core.column_positions import build_position_to_name
from normalize.core.domain import IssueSeverity, NormalizationIssue
from normalize.core.numeric_formats import NumericFormat, resolve_numeric_formats_by_canonical
from normalize.core.sql_helpers import read_columns
from normalize.core.token_policy import TokenPolicy
from normalize.stages.base import Stage
from suggestion.stages.shared_profiling import (
    DEFAULT_PROFILE_TABLE_NAME,
    ColumnProfile,
    ensure_column_profiles,
)
from suggestion.stages.type_inference.inference import infer_column_type

ISSUE_CODE_SEPARATOR_MISMATCH = "SEPARATOR_MISMATCH"
ISSUE_CODE_UNKNOWN_COLUMN_REFERENCE = "UNKNOWN_COLUMN_REFERENCE"


class TypeInferenceStage(Stage):
    """
    Infer column types from parse-success ratios.

    Rules:
    - Boolean threshold is configurable and required per run.
    - Integer/float threshold is configurable and required per run.
    - Currency threshold is configurable and required per run.
    - Priority: boolean -> integer -> float -> currency -> string.
    - Empty columns infer to string.

    Token policy inputs are mandatory and validated on every call:
    - `null_tokens`
    - `boolean_true_tokens`
    - `boolean_false_tokens`
    """

    def __init__(
        self,
        *,
        numeric_threshold: float,
        boolean_threshold: float,
        currency_threshold: float,
    ) -> None:
        super().__init__()
        if numeric_threshold <= 0.0 or numeric_threshold > 1.0:
            raise ValueError("numeric_threshold must be in (0, 1]")
        if boolean_threshold <= 0.0 or boolean_threshold > 1.0:
            raise ValueError("boolean_threshold must be in (0, 1]")
        if currency_threshold <= 0.0 or currency_threshold > 1.0:
            raise ValueError("currency_threshold must be in (0, 1]")
        self._numeric_threshold = numeric_threshold
        self._boolean_threshold = boolean_threshold
        self._currency_threshold = currency_threshold

    def execute(
        self,
        conn: DuckDBPyConnection,
        *,
        table_name: str = "raw_input",
        profile_table_name: str = DEFAULT_PROFILE_TABLE_NAME,
        null_tokens: list[str] | None,
        boolean_true_tokens: list[str] | None,
        boolean_false_tokens: list[str] | None,
        decimal_separator: str,
        thousand_separator: str,
        grouping_style: str,
        numeric_formats: Mapping[str, NumericFormat] | None,
        allow_leading_decimal_point: bool,
        currency_candidate_threshold: float,
        date_formats: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        start_time = perf_counter()
        token_policy = TokenPolicy.from_user_inputs(
            null_tokens=null_tokens,
            boolean_true_tokens=boolean_true_tokens,
            boolean_false_tokens=boolean_false_tokens,
        )
        columns_in_order = read_columns(conn, table_name)
        resolved_position_to_canonical = build_position_to_name(columns_in_order)
        declared_numeric_formats = dict(numeric_formats or {})
        resolved_numeric_formats_by_canonical = resolve_numeric_formats_by_canonical(
            numeric_formats=declared_numeric_formats,
            position_to_canonical=resolved_position_to_canonical,
        )

        profiles = ensure_column_profiles(
            conn,
            table_name=table_name,
            profile_table_name=profile_table_name,
            token_policy=token_policy,
            decimal_separator=decimal_separator,
            thousand_separator=thousand_separator,
            grouping_style=grouping_style,
            numeric_formats=numeric_formats,
            allow_leading_decimal_point=allow_leading_decimal_point,
            currency_candidate_threshold=currency_candidate_threshold,
        )
        declared_date_formats = dict(date_formats or {})
        resolved_issues = _resolve_unknown_position_keys(
            declared_date_formats=declared_date_formats,
            declared_numeric_formats=declared_numeric_formats,
            position_to_canonical=resolved_position_to_canonical,
        )
        resolved_date_formats_by_canonical = _resolve_date_formats_by_canonical(
            declared_date_formats=declared_date_formats,
            position_to_canonical=resolved_position_to_canonical,
        )

        inferred: dict[str, str] = {}
        detected_issues: list[NormalizationIssue] = list(resolved_issues)
        for column_name, profile in profiles.items():
            if column_name in resolved_date_formats_by_canonical:
                inferred[column_name] = "date"
                continue

            column_format = resolved_numeric_formats_by_canonical.get(column_name)
            column_decimal_separator = (
                decimal_separator if column_format is None else column_format.decimal_separator
            )
            column_thousand_separator = (
                thousand_separator if column_format is None else column_format.thousand_separator
            )

            inferred_type = infer_column_type(
                profile,
                numeric_threshold=self._numeric_threshold,
                boolean_threshold=self._boolean_threshold,
                currency_threshold=self._currency_threshold,
            )
            if _should_emit_separator_mismatch(
                profile=profile,
                inferred_type=inferred_type,
                numeric_threshold=self._numeric_threshold,
                thousand_separator=column_thousand_separator,
            ):
                detected_issues.append(
                    _build_separator_mismatch_issue(
                        column_name=column_name,
                        decimal_separator=column_decimal_separator,
                        thousand_separator=column_thousand_separator,
                        numeric_threshold=self._numeric_threshold,
                        declared_decimal_ratio=profile.decimal_ratio,
                        swapped_decimal_ratio=profile.swapped_decimal_ratio,
                    )
                )
            inferred[column_name] = inferred_type

        self.detected_issues = detected_issues

        self.metrics = {
            "duration_seconds": perf_counter() - start_time,
            "column_count": len(inferred),
            "numeric_threshold": self._numeric_threshold,
            "boolean_threshold": self._boolean_threshold,
            "currency_threshold": self._currency_threshold,
            "issue_count": len(detected_issues),
            "boolean_columns": sum(1 for value in inferred.values() if value == "boolean"),
            "integer_columns": sum(1 for value in inferred.values() if value == "integer"),
            "decimal_columns": sum(1 for value in inferred.values() if value == "decimal"),
            "currency_columns": sum(1 for value in inferred.values() if value == "currency"),
            "date_columns": sum(1 for value in inferred.values() if value == "date"),
            "string_columns": sum(1 for value in inferred.values() if value == "string"),
        }
        return inferred


def _resolve_unknown_position_keys(
    *,
    declared_date_formats: Mapping[str, str],
    declared_numeric_formats: Mapping[str, NumericFormat],
    position_to_canonical: Mapping[str, str],
) -> list[NormalizationIssue]:
    if not declared_date_formats and not declared_numeric_formats:
        return []
    issues: list[NormalizationIssue] = []
    for position_key in sorted({*declared_date_formats, *declared_numeric_formats}):
        if position_key not in position_to_canonical:
            issues.append(
                _build_unknown_column_reference_issue(position_key, len(position_to_canonical))
            )
    return issues


def _resolve_date_formats_by_canonical(
    *,
    declared_date_formats: Mapping[str, str],
    position_to_canonical: Mapping[str, str],
) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for position_key, format_string in declared_date_formats.items():
        canonical_name = position_to_canonical.get(position_key)
        if canonical_name is None:
            continue
        resolved[canonical_name] = format_string
    return resolved


def _should_emit_separator_mismatch(
    *,
    profile: ColumnProfile,
    inferred_type: str,
    numeric_threshold: float,
    thousand_separator: str,
) -> bool:
    if not thousand_separator:
        return False
    if inferred_type != "string":
        return False
    if profile.non_empty_count <= 0:
        return False
    return profile.swapped_decimal_ratio >= numeric_threshold


def _build_separator_mismatch_issue(
    *,
    column_name: str,
    decimal_separator: str,
    thousand_separator: str,
    numeric_threshold: float,
    declared_decimal_ratio: float,
    swapped_decimal_ratio: float,
) -> NormalizationIssue:
    return NormalizationIssue(
        code=ISSUE_CODE_SEPARATOR_MISMATCH,
        severity=IssueSeverity.WARNING,
        message=(
            f"Column {column_name!r} appears numeric with swapped separators "
            f"(declared decimal={decimal_separator!r}, thousand={thousand_separator!r})"
        ),
        location=column_name,
        evidence={
            "numeric_threshold": numeric_threshold,
            "declared_decimal_ratio": declared_decimal_ratio,
            "swapped_decimal_ratio": swapped_decimal_ratio,
            "declared_separators": {
                "decimal_separator": decimal_separator,
                "thousand_separator": thousand_separator,
            },
            "suggested_separators": {
                "decimal_separator": thousand_separator,
                "thousand_separator": decimal_separator,
            },
        },
    )


def _build_unknown_column_reference_issue(
    position_key: str, column_count: int
) -> NormalizationIssue:
    message = (
        f"date_formats position key {position_key!r} "
        f"is out of range for {column_count} columns"
    )
    return NormalizationIssue(
        code=ISSUE_CODE_UNKNOWN_COLUMN_REFERENCE,
        severity=IssueSeverity.WARNING,
        message=message,
        location=position_key,
        evidence={"position_key": position_key, "column_count": column_count},
    )
