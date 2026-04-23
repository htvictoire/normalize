"""Webhook dispatch for instance status transitions."""

from __future__ import annotations

import logging
from uuid import UUID

import requests

logger = logging.getLogger(__name__)


def fire_webhook(webhook_url: str, instance_id: UUID, status: str) -> None:
    try:
        requests.post(
            webhook_url,
            json={"instance_id": str(instance_id), "status": status},
            timeout=5,
        )
    except Exception:
        logger.exception("webhook delivery failed: url=%s instance=%s", webhook_url, instance_id)
