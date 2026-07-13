"""Celery tasks for background pipeline execution and maintenance."""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID

from app.worker.app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)  # type: ignore[misc]
def run_post_confirmation_pipeline(self: object, instance_id: str) -> None:  # type: ignore[misc]
    from app.bootstrap import MainOrchestrator  # noqa: PLC0415
    orchestrator = MainOrchestrator()
    uid = UUID(instance_id)
    try:
        orchestrator.profile(uid)
        orchestrator.normalize(uid)
    except Exception as exc:
        logger.exception("post-confirmation pipeline failed for instance %s", instance_id)
        retries: int = self.request.retries  # type: ignore[attr-defined]
        max_retries: int = self.max_retries  # type: ignore[attr-defined]
        if retries >= max_retries:
            # Out of retries: land the instance in a terminal state so callers
            # polling for completion stop waiting and learn why it died.
            orchestrator.mark_failed(uid, reason=f"{type(exc).__name__}: {exc}")
            raise
        raise self.retry(exc=exc) from exc  # type: ignore[attr-defined]


@celery_app.task  # type: ignore[misc]
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
