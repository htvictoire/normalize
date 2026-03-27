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

from conversion.stages.artifact_materialization.bundle import StagedArtifacts


@dataclass(frozen=True)
class LocalArtifactPublisher:
    """Publish artifact files to the local filesystem."""

    output_root: Path
    run_id: str | None = None

    @contextmanager
    def staging_root(self) -> Iterator[Path]:
        target_root = (
            self.output_root if self.run_id is None else self.output_root / self.run_id
        )
        target_root.mkdir(parents=True, exist_ok=True)
        yield target_root

    def publish(self, staged: StagedArtifacts) -> ArtifactPaths:
        return ArtifactPaths(
            normalized_parquet=str(staged.normalized_path),
            manifest_json=str(staged.manifest_path),
            trace_parquet=str(staged.trace_path),
        )


@dataclass(frozen=True)
class S3ArtifactPublisher:
    """Publish staged artifact files to S3-compatible object storage."""

    output_prefix: str
    run_id: str | None = None

    @contextmanager
    def staging_root(self) -> Iterator[Path]:
        with TemporaryDirectory(prefix="normalize-artifacts-") as temp_dir:
            yield Path(temp_dir)

    def publish(self, staged: StagedArtifacts) -> ArtifactPaths:
        prefix = _join_s3_key(_normalize_s3_prefix(self.output_prefix), self.run_id)
        normalized_key = _join_s3_key(prefix, staged.normalized_path.name)
        manifest_key = _join_s3_key(prefix, staged.manifest_path.name)
        trace_key = _join_s3_key(prefix, staged.trace_path.name)

        upload_s3_file(staged.normalized_path, s3_ref(normalized_key))
        upload_s3_file(staged.manifest_path, s3_ref(manifest_key))
        upload_s3_file(staged.trace_path, s3_ref(trace_key))

        return ArtifactPaths(
            normalized_parquet=normalized_key,
            manifest_json=manifest_key,
            trace_parquet=trace_key,
        )


ArtifactPublisher = LocalArtifactPublisher | S3ArtifactPublisher


def build_artifact_publisher(
    *,
    output_type: FileSource,
    output_root: str | Path,
    run_id: str | None = None,
) -> ArtifactPublisher:
    """Return the concrete artifact publisher for one output backend."""
    if output_type == "local":
        return LocalArtifactPublisher(output_root=Path(output_root), run_id=run_id)
    return S3ArtifactPublisher(output_prefix=str(output_root), run_id=run_id)


def _normalize_s3_prefix(prefix: str) -> str:
    cleaned = prefix.replace("\\", "/")
    parts = [part for part in cleaned.split("/") if part and part != "."]
    return "/".join(parts)


def _join_s3_key(prefix: str, leaf: str | None) -> str:
    if not leaf:
        return prefix
    if not prefix:
        return leaf
    return f"{prefix}/{leaf}"
