"""Artifact publication backends."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from shared.models.normalization import ArtifactPaths
from shared.models.operation import FileSource
from shared.storage.s3 import s3_ref, upload_s3_file

from conversion.artifacts.staging import StagedArtifacts


@dataclass(frozen=True)
class LocalArtifactPublisher:
    """Publish artifact files to the local filesystem."""

    output_root: Path
    run_id: str

    @contextmanager
    def staging_root(self) -> Iterator[Path]:
        self.output_root.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(
            dir=self.output_root,
            prefix=f".{self.run_id}.staging-",
        ) as temp_dir:
            yield Path(temp_dir)

    def publish(self, staged: StagedArtifacts) -> ArtifactPaths:
        target_root = self.output_root / self.run_id
        target_root.mkdir(parents=True, exist_ok=True)
        normalized_path = _promote_local_file(staged.normalized_path, target_root)
        manifest_path = _promote_local_file(staged.manifest_path, target_root)
        trace_path = _promote_local_file(staged.trace_path, target_root)
        return ArtifactPaths(
            normalized_parquet=str(normalized_path),
            manifest_json=str(manifest_path),
            trace_parquet=str(trace_path),
        )


@dataclass(frozen=True)
class S3ArtifactPublisher:
    """Publish staged artifact files to S3-compatible object storage."""

    output_prefix: str
    run_id: str

    @contextmanager
    def staging_root(self) -> Iterator[Path]:
        with TemporaryDirectory(prefix="normalize-artifacts-") as temp_dir:
            yield Path(temp_dir)

    def publish(self, staged: StagedArtifacts) -> ArtifactPaths:
        prefix = _join_s3_key(_normalize_s3_prefix(self.output_prefix), self.run_id)
        normalized_key = _join_s3_key(prefix, staged.normalized_path.name)
        manifest_key = _join_s3_key(prefix, staged.manifest_path.name)
        trace_key = _join_s3_key(prefix, staged.trace_path.name)

        # Publish the manifest last so its presence is the marker that the run is complete.
        upload_s3_file(staged.normalized_path, s3_ref(normalized_key))
        upload_s3_file(staged.trace_path, s3_ref(trace_key))
        upload_s3_file(staged.manifest_path, s3_ref(manifest_key))

        return ArtifactPaths(
            normalized_parquet=normalized_key,
            manifest_json=manifest_key,
            trace_parquet=trace_key,
        )


ArtifactPublisher = LocalArtifactPublisher | S3ArtifactPublisher


def build_artifact_publisher(
    output_type: FileSource,
    output_root: str | Path,
    run_id: str,
) -> ArtifactPublisher:
    """Return the concrete artifact publisher for one output backend."""
    if output_type == "local":
        return LocalArtifactPublisher(output_root=Path(output_root), run_id=run_id)
    return S3ArtifactPublisher(output_prefix=str(output_root), run_id=run_id)


def _normalize_s3_prefix(prefix: str) -> str:
    cleaned = prefix.replace("\\", "/")
    parts = [part for part in cleaned.split("/") if part and part != "."]
    return "/".join(parts)


def _join_s3_key(prefix: str, leaf: str) -> str:
    if not prefix:
        return leaf
    return f"{prefix}/{leaf}"


def _promote_local_file(staged_path: Path, target_root: Path) -> Path:
    target_path = target_root / staged_path.name
    staged_path.replace(target_path)
    return target_path
