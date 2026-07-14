"""Webhook delivery. The payload shape is the WebhookEvent contract."""

from __future__ import annotations

import logging

import requests

from shared.models.webhook import WebhookEvent

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 5


def send_webhook(webhook_url: str, event: WebhookEvent) -> None:
    try:
        requests.post(webhook_url, json=event.model_dump(mode="json"), timeout=_TIMEOUT_SECONDS)
    except Exception:
        logger.exception(
            "webhook delivery failed: url=%s instance=%s", webhook_url, event.instance_id
        )
