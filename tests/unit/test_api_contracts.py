import pytest
from pydantic import ValidationError

from app.api.models import ConfirmRequest


def _operation_payload() -> dict[str, object]:
    return {
        "null_tokens": ["", "null", "none", "n/a", "-"],
        "assign_indices": True,
        "drop_empty_rows": True,
        "full_raw_row": False,
        "include_unique_ratio": True,
        "include_per_column_parse_error_counts": False,
        "approximate_unique": False,
        "trace_mode": "sparse",
        "decision_thresholds": {"ready": 95.0, "warning": 85.0},
    }


def _source_format_payload() -> dict[str, object]:
    return {
        "format_type": "csv",
        "encoding": "utf-8",
        "delimiter": ",",
        "header_mode": "present",
        "header_row_index": 1,
    }


def _column_config_payload() -> dict[str, dict[str, str]]:
    return {"A": {"type": "string"}}


def _config_payload() -> dict[str, object]:
    return {
        "source_format": _source_format_payload(),
        "column_config": _column_config_payload(),
        "operation_config": _operation_payload(),
    }


def test_confirm_request_requires_source_format() -> None:
    config = _config_payload()
    del config["source_format"]

    with pytest.raises(ValidationError):
        ConfirmRequest(config=config)


def test_confirm_request_requires_column_config() -> None:
    config = _config_payload()
    del config["column_config"]

    with pytest.raises(ValidationError):
        ConfirmRequest(config=config)


def test_confirm_request_requires_operation_config() -> None:
    config = _config_payload()
    del config["operation_config"]

    with pytest.raises(ValidationError):
        ConfirmRequest(config=config)


def test_confirm_request_accepts_auto_normalize_flag() -> None:
    request = ConfirmRequest(config=_config_payload(), auto_normalize=True)

    assert request.auto_normalize is True
