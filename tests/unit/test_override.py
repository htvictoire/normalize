import pytest

from normalize.config.override import apply_override_layers


def test_override_layers_reject_source_format_fields() -> None:
    with pytest.raises(
        ValueError, match="workspace override cannot set source-format fields"
    ):
        apply_override_layers(
            {"threads": 4, "encoding": "utf-8"},
            workspace={"decimal_separator": ",", "threads": 8},
        )


def test_override_layers_allow_operational_fields() -> None:
    merged = apply_override_layers(
        {"threads": 4, "trace_mode": "full"},
        rules={"decision_ready_threshold": 95.0},
        template={"drop_empty_rows": True},
        workspace={"threads": 8, "trace_mode": "sparse"},
    )
    assert merged["threads"] == 8
    assert merged["trace_mode"] == "sparse"
    assert merged["decision_ready_threshold"] == 95.0
    assert merged["drop_empty_rows"] is True
