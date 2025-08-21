from pathlib import Path

import pytest
from pydantic import ValidationError

from app.api.models import ConfirmRequest, NormalizeRequest


def _operation_payload() -> dict[str, object]:
    return {
        "null_tokens": ["", "null", "none", "n/a", "-"],
        "boolean_true_tokens": ["true", "yes", "1"],
        "boolean_false_tokens": ["false", "no", "0"],
        "assign_indices": True,
        "drop_empty_rows": True,
        "emit_raw_row": True,
        "full_raw_row": False,
        "emit_parse_issues": True,
        "include_unique_ratio": True,
        "include_per_column_parse_error_counts": False,
        "approximate_unique": False,
        "trace_mode": "sparse",
        "decision_thresholds": {"ready": 95.0, "warning": 85.0},
    }


def _source_format_payload() -> dict[str, object]:
    return {
        "encoding": "utf-8",
        "delimiter": ",",
        "header_mode": "present",
        "header_row_index": 1,
    }


def _column_config_payload() -> dict[str, dict[str, str]]:
    return {"A": {"type": "string"}}


def test_confirm_request_requires_source_format() -> None:
    with pytest.raises(ValidationError):
        ConfirmRequest(
            column_config=_column_config_payload(),
            operation_config=_operation_payload(),
        )


def test_confirm_request_requires_column_config() -> None:
    with pytest.raises(ValidationError):
        ConfirmRequest(
            source_format=_source_format_payload(),
            operation_config=_operation_payload(),
        )


def test_confirm_request_requires_operation_config() -> None:
    with pytest.raises(ValidationError):
        ConfirmRequest(
            source_format=_source_format_payload(),
            column_config=_column_config_payload(),
        )


def test_normalize_request_rejects_config_overrides() -> None:
    with pytest.raises(ValidationError):
        NormalizeRequest(
            output_dir=Path("data/manual_runs"),
            mode="APPLY",
            rules_version="v1",
            column_config=_column_config_payload(),
            operation_config=_operation_payload(),
        )
