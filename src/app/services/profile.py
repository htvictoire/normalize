"""Profile phase application service."""

from __future__ import annotations

from profile.pipeline import run_profile

from app.models.instance import InstanceModel, InstanceStatus


class ProfileService:
    """Run mandatory full-dataset profile phase for a confirmed instance."""

    def profile(self, instance: InstanceModel) -> InstanceModel:
        if instance.status is not InstanceStatus.CONFIRMED:
            raise ValueError("instance must be CONFIRMED before profile")
        if instance.confirmed_column_config is None or instance.operation_config is None:
            raise ValueError("instance is missing confirmed config")

        instance.status = InstanceStatus.PROFILING
        profile_output = run_profile(
            file_path=instance.source_r2_url,
            source_format=instance.source_format,
            column_config=dict(instance.confirmed_column_config),
            operation_config=instance.operation_config,
        )
        instance.set_profile_output(profile_output=profile_output)
        return instance
