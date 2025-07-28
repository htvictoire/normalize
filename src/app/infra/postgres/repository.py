"""PostgreSQL repository implementation for normalization instances."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from app.models.instance import InstanceModel
from app.persistence.serialization import instance_to_record, record_to_instance

try:
    import psycopg as _psycopg_module  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - exercised when dependency is missing at runtime
    _psycopg_module = None


class PostgresRunRepository:
    """Persist normalization runs in PostgreSQL with one JSON payload column."""

    def __init__(self, *, dsn: str) -> None:
        self._dsn = dsn
        self._psycopg = _load_psycopg()
        self._ensure_schema()

    def save(self, instance: InstanceModel) -> InstanceModel:
        payload = json.dumps(instance_to_record(instance), separators=(",", ":"))
        with self._psycopg.connect(self._dsn, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO normalization_runs (id, tenant_id, status, payload)
                VALUES (%s, %s, %s, %s::jsonb)
                ON CONFLICT (id) DO UPDATE
                SET tenant_id = EXCLUDED.tenant_id,
                    status = EXCLUDED.status,
                    payload = EXCLUDED.payload,
                    updated_at = NOW()
                """,
                (
                    str(instance.id),
                    instance.tenant_id,
                    instance.status.value,
                    payload,
                ),
            )
        return instance

    def get(self, instance_id: UUID) -> InstanceModel | None:
        with self._psycopg.connect(self._dsn, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT payload FROM normalization_runs WHERE id = %s",
                (str(instance_id),),
            )
            row = cur.fetchone()
        if row is None:
            return None
        payload = row[0]
        if isinstance(payload, str):
            loaded: Any = json.loads(payload)
        else:
            loaded = payload
        return record_to_instance(loaded)

    def get_required(self, instance_id: UUID) -> InstanceModel:
        instance = self.get(instance_id)
        if instance is None:
            raise KeyError(f"instance not found: {instance_id}")
        return instance

    def _ensure_schema(self) -> None:
        with self._psycopg.connect(self._dsn, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS normalization_runs (
                    id UUID PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )


def _load_psycopg() -> Any:
    if _psycopg_module is None:
        raise RuntimeError(
            "psycopg is required for Postgres repository. "
            "Install dependencies with `pip install -e '.[dev]'`."
        )
    return _psycopg_module
