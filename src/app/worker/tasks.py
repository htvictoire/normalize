"""Celery maintenance tasks."""

from __future__ import annotations

import logging
from pathlib import Path

from app.worker.app import celery_app

logger = logging.getLogger(__name__)


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
