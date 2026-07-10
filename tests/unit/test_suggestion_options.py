import pytest
from pydantic import ValidationError

from shared.models.instance import InstanceModel

from app.api.models import SuggestRequest
from app.persistence.serialization import instance_to_record, record_to_instance


def _suggest_payload() -> dict[str, object]:
    return {
        "source_file": "input.csv",
        "source_file_name": "input.csv",
        "source_type": "local",
        "source_file_format": "csv",
        "source_checksum": "a" * 64,
        "suggestion_method": "rule_based",
        "extended_type_detection": False,
    }


def test_suggest_request_requires_extended_type_detection() -> None:
    payload = _suggest_payload()
    del payload["extended_type_detection"]

    with pytest.raises(ValidationError):
        SuggestRequest.model_validate(payload)


def test_suggest_request_accepts_explicit_extended_type_detection() -> None:
    request = SuggestRequest.model_validate(_suggest_payload())

    assert request.extended_type_detection is False


def test_instance_serialization_round_trips_extended_type_detection() -> None:
    instance = InstanceModel.create(
        source_file="input.csv",
        source_file_name="input.csv",
        source_type="local",
        source_file_format="csv",
        source_checksum="a" * 64,
        suggestion_method="rule_based",
        extended_type_detection=True,
    )

    record = instance_to_record(instance)
    restored = record_to_instance(record)

    assert record["extended_type_detection"] is True
    assert restored.extended_type_detection is True
