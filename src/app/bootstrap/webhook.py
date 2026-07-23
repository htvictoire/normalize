"""Webhook delivery of the complete instance state."""

from __future__ import annotations

import logging

import requests

from shared.models.instance import InstanceModel

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 5


def send_webhook(webhook_url: str, instance: InstanceModel) -> None:
    try:
        requests.post(
            webhook_url,
            json=instance.model_dump(mode="json"),
            timeout=_TIMEOUT_SECONDS,
        )
    except Exception:
        logger.exception(
            "webhook delivery failed: url=%s instance=%s",
            webhook_url,
            instance.instance_id,
        )
