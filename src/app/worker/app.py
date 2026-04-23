"""Celery application instance and Beat schedule."""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from shared.settings import get_settings


def _create_celery_app() -> Celery:
    settings = get_settings()
    app = Celery(
        "normalize",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=["app.worker.tasks"],
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        beat_schedule={
            "sweep-stuck-normalizing": {
                "task": "app.worker.tasks.sweep_stuck_jobs",
                "schedule": crontab(minute="*/5"),
            }
        },
    )
    return app


celery_app = _create_celery_app()
