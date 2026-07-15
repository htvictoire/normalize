"""PostgreSQL repository implementation for normalization instances."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from shared.errors import InstanceNotFoundError
from shared.models.instance import InstanceModel

from app.persistence.serialization import instance_to_record, record_to_instance

_psycopg_module: Any

try:
    import psycopg as _psycopg_module
except ImportError:  # pragma: no cover - exercised when dependency is missing at runtime
    _psycopg_module = None


def _as_jsonb(value: Any) -> str | None:
    """Serialize a dict to a JSON string for a JSONB column, or None for SQL NULL."""
    if value is None:
        return None
    return json.dumps(value, separators=(",", ":"))


class PostgresRunRepository:
    """Persist normalization runs in PostgreSQL, one column per InstanceModel field."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._psycopg = _load_psycopg()
        self._ensure_schema()

    def save(self, instance: InstanceModel) -> InstanceModel:
        r = instance_to_record(instance)
        with self._psycopg.connect(self._dsn, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO normalization_runs (
                    instance_id, tenant_id, status, webhook_url,
                    source_file, source_file_name, source_file_format,
                    source_type, source_checksum, suggestion_method,
                    extended_type_detection,
                    suggested_config, suggestion_display, suggestion_confidence,
                    confirmed_config, profiling_output, normalization_output,
                    failure_reason, timings, issues_by_phase
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s,
                    %s::jsonb, %s::jsonb, %s::jsonb,
                    %s::jsonb, %s::jsonb, %s::jsonb,
                    %s, %s::jsonb, %s::jsonb
                )
                ON CONFLICT (instance_id) DO UPDATE SET
                    status                = EXCLUDED.status,
                    webhook_url           = EXCLUDED.webhook_url,
                    suggested_config      = EXCLUDED.suggested_config,
                    suggestion_display    = EXCLUDED.suggestion_display,
                    suggestion_confidence = EXCLUDED.suggestion_confidence,
                    confirmed_config      = EXCLUDED.confirmed_config,
                    profiling_output      = EXCLUDED.profiling_output,
                    normalization_output  = EXCLUDED.normalization_output,
                    failure_reason        = EXCLUDED.failure_reason,
                    timings               = EXCLUDED.timings,
                    issues_by_phase       = EXCLUDED.issues_by_phase,
                    updated_at            = NOW()
                """,
                (
                    r["instance_id"], r["tenant_id"], r["status"], r["webhook_url"],
                    r["source_file"], r["source_file_name"], r["source_file_format"],
                    r["source_type"], r["source_checksum"], r["suggestion_method"],
                    r["extended_type_detection"],
                    _as_jsonb(r["suggested_config"]),
                    _as_jsonb(r["suggestion_display"]),
                    _as_jsonb(r["suggestion_confidence"]),
                    _as_jsonb(r["confirmed_config"]),
                    _as_jsonb(r["profiling_output"]),
                    _as_jsonb(r["normalization_output"]),
                    r["failure_reason"],
                    _as_jsonb(r["timings"]),
                    _as_jsonb(r["issues_by_phase"]),
                ),
            )
        return instance

    def get(self, instance_id: UUID) -> InstanceModel | None:
        with self._psycopg.connect(self._dsn, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT instance_id, tenant_id, status, webhook_url,
                       source_file, source_file_name, source_file_format,
                       source_type, source_checksum, suggestion_method,
                       extended_type_detection,
                       suggested_config, suggestion_display, suggestion_confidence,
                       confirmed_config, profiling_output, normalization_output,
                       failure_reason, timings, issues_by_phase
                FROM normalization_runs
                WHERE instance_id = %s
                """,
                (str(instance_id),),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return record_to_instance({
            "instance_id":          row[0],
            "tenant_id":            row[1],
            "status":               row[2],
            "webhook_url":          row[3],
            "source_file":          row[4],
            "source_file_name":     row[5],
            "source_file_format":   row[6],
            "source_type":          row[7],
            "source_checksum":      row[8],
            "suggestion_method":    row[9],
            "extended_type_detection": row[10],
            "suggested_config":     row[11],
            "suggestion_display":   row[12],
            "suggestion_confidence": row[13],
            "confirmed_config":     row[14],
            "profiling_output":     row[15],
            "normalization_output": row[16],
            "failure_reason":       row[17],
            "timings":              row[18],
            "issues_by_phase":      row[19],
        })

    def get_required(self, instance_id: UUID) -> InstanceModel:
        instance = self.get(instance_id)
        if instance is None:
            raise InstanceNotFoundError(f"instance not found: {instance_id}")
        return instance

    def sweep_stuck_jobs(self, threshold_minutes: int = 30) -> list[UUID]:
        """Fail instances stranded in any in-flight phase past the threshold.

        PROFILING strands just as easily as NORMALIZING — a sweeper that only
        watches one of them leaves the other stuck forever.
        """
        from datetime import timedelta  # noqa: PLC0415

        with self._psycopg.connect(self._dsn, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE normalization_runs
                SET status = 'FAILED',
                    failure_reason = 'stranded in ' || status || ' past threshold',
                    updated_at = NOW()
                WHERE status IN ('PROFILING', 'NORMALIZING', 'RETRYING')
                  AND updated_at < NOW() - %s
                RETURNING instance_id
                """,
                (timedelta(minutes=threshold_minutes),),
            )
            rows = cur.fetchall()
        return [UUID(str(row[0])) for row in rows]

    def _ensure_schema(self) -> None:
        with self._psycopg.connect(self._dsn, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS normalization_runs (
                    instance_id          UUID        PRIMARY KEY,
                    tenant_id            TEXT        NOT NULL,
                    status               TEXT        NOT NULL,
                    webhook_url          TEXT,
                    source_file          TEXT        NOT NULL,
                    source_file_name     TEXT        NOT NULL,
                    source_file_format   TEXT        NOT NULL,
                    source_type          TEXT        NOT NULL,
                    source_checksum      TEXT        NOT NULL,
                    suggestion_method     TEXT        NOT NULL DEFAULT 'rule_based',
                    extended_type_detection BOOLEAN   NOT NULL DEFAULT FALSE,
                    suggested_config      JSONB,
                    suggestion_display    JSONB,
                    suggestion_confidence JSONB,
                    confirmed_config      JSONB,
                    profiling_output      JSONB,
                    normalization_output  JSONB,
                    failure_reason        TEXT,
                    timings               JSONB,
                    issues_by_phase       JSONB,
                    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                """
                ALTER TABLE normalization_runs
                    ADD COLUMN IF NOT EXISTS suggestion_method TEXT NOT NULL DEFAULT 'rule_based'
                """
            )
            cur.execute(
                """
                ALTER TABLE normalization_runs
                    ADD COLUMN IF NOT EXISTS extended_type_detection BOOLEAN NOT NULL DEFAULT FALSE
                """
            )
            cur.execute(
                """
                ALTER TABLE normalization_runs
                    ADD COLUMN IF NOT EXISTS suggestion_confidence JSONB
                """
            )
            cur.execute(
                """
                ALTER TABLE normalization_runs
                    ADD COLUMN IF NOT EXISTS failure_reason TEXT
                """
            )
            cur.execute(
                """
                ALTER TABLE normalization_runs
                    ADD COLUMN IF NOT EXISTS issues_by_phase JSONB
                """
            )


def _load_psycopg() -> Any:
    if _psycopg_module is None:
        raise RuntimeError(
            "psycopg is required for Postgres repository. "
            "Install dependencies with `pip install -e '.[dev]'`."
        )
    return _psycopg_module
