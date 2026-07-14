"""S3-compatible object storage client utilities."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

import boto3
from botocore.exceptions import ClientError

from shared.errors import SourceError
from shared.settings import get_settings

# Real S3 signals a missing object by error code; some compatible stores set only
# the HTTP status. "404" covers both since the status is compared as a string.
_S3_NOT_FOUND_CODES = frozenset({"NoSuchKey", "NoSuchBucket", "NotFound", "404"})


def _is_not_found(exc: ClientError) -> bool:
    """Whether a ClientError means the requested object does not exist."""
    error = exc.response.get("Error", {})
    status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    return error.get("Code") in _S3_NOT_FOUND_CODES or str(status) in _S3_NOT_FOUND_CODES


@dataclass(frozen=True)
class S3ObjectRef:
    """Stable object reference for one S3-compatible source."""

    bucket: str
    key: str


class _S3ClientProtocol(Protocol):
    def get_object(self, **kwargs: Any) -> dict[str, Any]: ...

    def download_fileobj(self, *args: Any, **kwargs: Any) -> None: ...

    def upload_fileobj(self, *args: Any, **kwargs: Any) -> None: ...


def _build_s3_client() -> _S3ClientProtocol:
    settings = get_settings()
    return cast(
        _S3ClientProtocol,
        boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            region_name="auto",
        ),
    )


def s3_ref(key: str) -> S3ObjectRef:
    """Resolve a storage key to an S3ObjectRef using the configured bucket."""
    return S3ObjectRef(bucket=get_settings().s3_bucket, key=key)


def fetch_s3_probe(obj: S3ObjectRef, n_bytes: int) -> bytes:
    """Read the first `n_bytes` from an S3-compatible object."""
    if n_bytes < 1:
        raise ValueError("n_bytes must be >= 1")

    client = _build_s3_client()
    try:
        response = client.get_object(
            Bucket=obj.bucket,
            Key=obj.key,
            Range=f"bytes=0-{n_bytes - 1}",
        )
    except ClientError as exc:
        if _is_not_found(exc):
            raise SourceError(f"Source object not found: {obj.key!r}") from exc
        raise
    body = response["Body"]
    try:
        return bytes(body.read())
    finally:
        body.close()


def download_s3_temp(obj: S3ObjectRef) -> Path:
    """Download an S3-compatible object to a temporary local file."""
    client = _build_s3_client()
    suffix = Path(obj.key).suffix or ".tmp"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="normalize-s3-",
            suffix=suffix,
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            client.download_fileobj(obj.bucket, obj.key, temp_file)
    except Exception as exc:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        if isinstance(exc, ClientError) and _is_not_found(exc):
            raise SourceError(f"Source object not found: {obj.key!r}") from exc
        raise
    return temp_path


def upload_s3_file(local_path: Path, obj: S3ObjectRef) -> None:
    """Upload one local file to an S3-compatible object key."""
    client = _build_s3_client()
    with local_path.open("rb") as handle:
        client.upload_fileobj(handle, obj.bucket, obj.key)


def build_duckdb_s3_url(obj: S3ObjectRef) -> str:
    """Return the DuckDB-compatible `s3://bucket/key` URL for one object."""
    return f"s3://{obj.bucket}/{obj.key}"


__all__ = [
    "S3ObjectRef",
    "build_duckdb_s3_url",
    "download_s3_temp",
    "fetch_s3_probe",
    "s3_ref",
    "upload_s3_file",
]
