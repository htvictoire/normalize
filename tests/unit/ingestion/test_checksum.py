import hashlib

from shared.ingestion.checksum import sha256_stream


def test_sha256_stream_matches_hashlib(tmp_path) -> None:
    payload = ("x" * 10000).encode("utf-8")
    path = tmp_path / "payload.csv"
    path.write_bytes(payload)

    assert sha256_stream(path, chunk_size=1024) == hashlib.sha256(payload).hexdigest()
