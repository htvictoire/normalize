"""Serialization helpers for persistence of normalization instances."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import TypeAdapter

from shared.models.instance import InstanceModel, StageTimings
from shared.models.instance_config import InstanceConfig
from shared.models.issues import NormalizationIssue
from shared.models.normalization import NormalizationOutput
from shared.models.profiling import ProfilingOutput
from shared.models.suggestion import SuggestionConfidence, SuggestionDisplay

_ISSUES_BY_PHASE = TypeAdapter(dict[str, list[NormalizationIssue]])


def instance_to_record(instance: InstanceModel) -> dict[str, Any]:
    """Serialize one instance to a column-mapped record."""
    return {
        "instance_id": str(instance.instance_id),
        "tenant_id": instance.tenant_id,
        "status": instance.status,
        "source_file": instance.source_file,
        "source_file_name": instance.source_file_name,
        "source_file_format": instance.source_file_format,
        "source_type": instance.source_type,
        "source_checksum": instance.source_checksum,
        "suggestion_method": instance.suggestion_method,
        "extended_type_detection": instance.extended_type_detection,
        "webhook_url": instance.webhook_url,
        "suggested_config": (
            instance.suggested_config.model_dump(mode="json")
            if instance.suggested_config is not None
            else None
        ),
        "suggestion_display": (
            instance.suggestion_display.model_dump(mode="json")
            if instance.suggestion_display is not None
            else None
        ),
        "suggestion_confidence": (
            instance.suggestion_confidence.model_dump(mode="json")
            if instance.suggestion_confidence is not None
            else None
        ),
        "confirmed_config": (
            instance.confirmed_config.model_dump(mode="json")
            if instance.confirmed_config is not None
            else None
        ),
        "profiling_output": (
            instance.profiling_output.model_dump(mode="json")
            if instance.profiling_output is not None
            else None
        ),
        "normalization_output": (
            instance.normalization_output.model_dump(mode="json")
            if instance.normalization_output is not None
            else None
        ),
        "failure_reason": instance.failure_reason,
        "timings": instance.timings.model_dump(mode="json"),
        "issues_by_phase": _ISSUES_BY_PHASE.dump_python(instance.issues_by_phase, mode="json"),
    }


def record_to_instance(record: Mapping[str, Any]) -> InstanceModel:
    """Deserialize a column-mapped record into a strict instance."""
    return InstanceModel(
        instance_id=record["instance_id"],
        tenant_id=record["tenant_id"],
        status=record["status"],
        webhook_url=record.get("webhook_url"),
        source_file=record["source_file"],
        source_file_name=record["source_file_name"],
        source_file_format=record["source_file_format"],
        source_type=record["source_type"],
        source_checksum=record["source_checksum"],
        suggestion_method=record["suggestion_method"],
        extended_type_detection=record["extended_type_detection"],
        suggested_config=(
            InstanceConfig.model_validate(record["suggested_config"])
            if record.get("suggested_config") is not None
            else None
        ),
        suggestion_display=(
            SuggestionDisplay.model_validate(record["suggestion_display"])
            if record.get("suggestion_display") is not None
            else None
        ),
        suggestion_confidence=(
            SuggestionConfidence.model_validate(record["suggestion_confidence"])
            if record.get("suggestion_confidence") is not None
            else None
        ),
        confirmed_config=(
            InstanceConfig.model_validate(record["confirmed_config"])
            if record.get("confirmed_config") is not None
            else None
        ),
        failure_reason=record.get("failure_reason"),
        profiling_output=(
            ProfilingOutput.model_validate(record["profiling_output"])
            if record.get("profiling_output") is not None
            else None
        ),
        normalization_output=(
            NormalizationOutput.model_validate(record["normalization_output"])
            if record.get("normalization_output") is not None
            else None
        ),
        timings=StageTimings.model_validate(record["timings"]),
        issues_by_phase=(
            _ISSUES_BY_PHASE.validate_python(record["issues_by_phase"])
            if record.get("issues_by_phase") is not None
            else {}
        ),
    )
