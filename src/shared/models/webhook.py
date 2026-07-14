"""Webhook payload contract — the single shape delivered on every notification.

One event per completed step: the instance's current status and every issue raised
so far. New evolving state is added by extending this model and populating it in the
orchestrator's single dispatch point — nowhere else.
"""

from __future__ import annotations

from shared.models.base import MainModel
from shared.models.instance import InstanceStatus
from shared.models.issues import NormalizationIssue


class WebhookEvent(MainModel):
    """One webhook delivery: the instance's status and the issues accumulated so far."""

    instance_id: str
    status: InstanceStatus
    issues: list[NormalizationIssue]
