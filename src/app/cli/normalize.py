"""Call local API normalize endpoint using suggestion.json payload."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests
from requests import Response

from shared.settings import get_settings


def main() -> None:
    defaults = ["data/suggestion.json", "APPLY", "data/normalization.json"]
    suggestion_json, mode, out_json = (sys.argv[1:] + defaults)[: len(defaults)]
    suggestion_path = Path(suggestion_json)
    instance_payload = json.loads(suggestion_path.read_text(encoding="utf-8"))
    if not isinstance(instance_payload, dict):
        raise TypeError("suggestion.json must contain one instance object")
    instance_id = str(instance_payload["id"])
    output_dir = Path("data/manual_runs") / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    normalize_payload = {
        "output_dir": str(output_dir),
        "mode": mode,
        "rules_version": "v1",
    }

    settings = get_settings()
    base_url = settings.api_base_url.rstrip("/")
    timeout_seconds = _request_timeout_seconds()
    _ensure_api_ready(base_url)
    normalize_url = f"{base_url}/normalize/instances/{instance_id}/normalize"
    print(
        f"Submitting normalize request to {normalize_url} "
        f"(mode={mode}, timeout={timeout_seconds}s)..."
    )
    response = requests.post(
        normalize_url,
        json=normalize_payload,
        timeout=(5, timeout_seconds),
    )
    _raise_for_status_with_body(response)
    result = response.json()

    out_path = Path(out_json)
    out_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, ensure_ascii=True, sort_keys=True))


def _request_timeout_seconds() -> int:
    raw = os.getenv("NORMALIZE_APPLY_TIMEOUT_SECONDS", "7200")
    value = int(raw)
    if value <= 0:
        raise ValueError("NORMALIZE_APPLY_TIMEOUT_SECONDS must be a positive integer")
    return value


def _ensure_api_ready(base_url: str) -> None:
    health_url = f"{base_url.rstrip('/')}/health"
    try:
        response = requests.get(health_url, timeout=(3, 3))
        _raise_for_status_with_body(response)
    except requests.RequestException as exc:
        raise RuntimeError(
            "Normalization API is not reachable. "
            f"Start it with `make api` and verify {health_url}."
        ) from exc


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
