"""Normalization-phase application service."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from app.models.instance import InstanceModel, InstanceStatus, NormalizationOutput
from app.services.normalization.execution import execute_normalization
from app.services.normalization.result import NormalizationResult
from shared.models.column import ColumnConfig
from shared.models.issues import IssueSeverity
from shared.models.operation import OperationConfig, RunMode
from shared.settings import get_settings


class NormalizationService:
    """Run normalization after confirmed suggestion output."""

    def confirm_instance(
        self,
        instance: InstanceModel,
        *,
        confirmed_column_config: Mapping[str, ColumnConfig],
        operation_config: OperationConfig,
    ) -> InstanceModel:
        """Persist caller confirmation on the run instance."""
        instance.confirm(
            confirmed_column_config=dict(confirmed_column_config),
            operation_config=operation_config,
        )
        return instance

    def normalize(
        self,
        instance: InstanceModel,
        *,
        output_dir: str | Path,
        mode: RunMode = "APPLY",
        rules_version: str = "v1",
    ) -> NormalizationResult:
        """Execute normalization phase using confirmed config from one instance."""
        if instance.status is not InstanceStatus.PROFILED:
            raise ValueError("instance must be PROFILED before normalize")
        if instance.profile_output is not None and any(
            issue.severity is IssueSeverity.ERROR for issue in instance.profile_output.issues
        ):
            raise ValueError("instance has blocking profile issues")

        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)
        settings = get_settings()

        result = execute_normalization(
            instance,
            output_root=output_root,
            run_mode=mode,
            rules_version=rules_version,
            duckdb_memory_limit=settings.duckdb_memory_limit,
        )

        artifacts = result["artifacts"] if mode == "APPLY" else None

        instance.status = InstanceStatus(result["status"])
        instance.normalization_output = NormalizationOutput(
            fingerprint=result["fingerprint"],
            artifacts=artifacts,
        )
        return NormalizationResult(
            instance=instance,
            status=instance.status.value,
            fingerprint=result["fingerprint"],
            artifacts=artifacts,
        )
