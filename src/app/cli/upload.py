"""Call local API suggest endpoint and write suggestion.json."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests
from requests import Response

from shared.settings import get_settings


def main() -> None:
    defaults = ["data/prod_like_10m.csv", "data/suggestion.json"]
    csv_path, out_json = (sys.argv[1:] + defaults)[: len(defaults)]

    source_path = Path(csv_path)
    payload = {
        "name": source_path.name,
        "file": _to_file_name(source_path),
    }

    settings = get_settings()
    base_url = settings.api_base_url.rstrip("/")
    url = f"{base_url}/normalize/suggest"
    timeout_seconds = _request_timeout_seconds()
    _ensure_api_ready(base_url)
    _print_submission_message(source_path, url, timeout_seconds)

    response = requests.post(url, json=payload, timeout=(5, timeout_seconds))
    _raise_for_status_with_body(response)
    data = response.json()

    out_path = Path(out_json)
    out_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(data, indent=2, ensure_ascii=True, sort_keys=True))


def _to_file_name(path: Path) -> str:
    if path.is_absolute():
        return str(path)
    if path.parts and path.parts[0] == "data":
        return path.name
    return str(path)


def _request_timeout_seconds() -> int:
    raw = os.getenv("NORMALIZE_UPLOAD_TIMEOUT_SECONDS", "3600")
    value = int(raw)
    if value <= 0:
        raise ValueError("NORMALIZE_UPLOAD_TIMEOUT_SECONDS must be a positive integer")
    return value


def _ensure_api_ready(base_url: str) -> None:
    health_url = f"{base_url}/health"
    try:
        response = requests.get(health_url, timeout=(3, 3))
        _raise_for_status_with_body(response)
    except requests.RequestException as exc:
        raise RuntimeError(
            "Normalization API is not reachable. "
            f"Start it with `make api` and verify {health_url}."
        ) from exc


def _print_submission_message(source_path: Path, url: str, timeout_seconds: int) -> None:
    size_mb = source_path.stat().st_size / (1024 * 1024)
    print(
        f"Submitting suggest request to {url} for {source_path} "
        f"({size_mb:.1f} MB), timeout={timeout_seconds}s..."
    )


def _raise_for_status_with_body(response: Response) -> None:
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        body = response.text.strip()
        if body:
            raise RuntimeError(
                f"HTTP {response.status_code} from API: {body}"
            ) from exc
        raise
