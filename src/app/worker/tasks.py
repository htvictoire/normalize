"""Celery tasks: scheduled suggestion runs and maintenance."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from uuid import UUID

from app.worker.app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task  # type: ignore[untyped-decorator]
def run_suggestion_task(instance_id: str, request_payload: dict[str, Any]) -> None:
    """Run the full suggest pipeline for an already-created instance and persist it.

    The instance is created and saved synchronously by the caller before this is
    scheduled, so a failure here has somewhere to record itself rather than being
    lost with no trace.
    """
    from shared.models.suggestion import SuggestionInput  # noqa: PLC0415
    from shared.settings import get_settings  # noqa: PLC0415

    from app.bootstrap.suggestion import SuggestionService  # noqa: PLC0415
    from app.bootstrap.webhook import send_webhook  # noqa: PLC0415
    from app.infra.postgres.repository import PostgresRunRepository  # noqa: PLC0415

    settings = get_settings()
    repo = PostgresRunRepository(settings.postgres_dsn)
    instance = repo.get_required(UUID(instance_id))
    request = SuggestionInput.model_validate(request_payload)
    try:
        layout, typing = SuggestionService().suggest(request)
        instance.set_layout_output(layout)
        instance.set_typing_output(typing)
    except Exception as exc:
        logger.exception("scheduled suggestion failed for instance %s", instance_id)
        instance.fail(f"{type(exc).__name__}: {exc}")
    repo.save(instance)
    if instance.webhook_url:
        send_webhook(instance.webhook_url, instance)


@celery_app.task  # type: ignore[untyped-decorator]
def sweep_stuck_jobs() -> None:
    from shared.settings import get_settings  # noqa: PLC0415

    from app.infra.postgres.repository import PostgresRunRepository  # noqa: PLC0415

    settings = get_settings()
    repo = PostgresRunRepository(settings.postgres_dsn)
    stuck_ids = repo.sweep_stuck_jobs()
    cache_dir = Path(settings.duckdb_cache_dir)
    for instance_id in stuck_ids:
        cache_file = cache_dir / f"{instance_id}.duckdb"
        if cache_file.exists():
            cache_file.unlink()
        logger.info("recovered stuck instance %s", instance_id)
