"""Production infrastructure health checks for Temporal and ClickHouse."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.services.clickhouse_service import get_clickhouse_service
from app.temporal.worker import get_temporal_client, registered_workflow_names, temporal_configured

logger = get_logger(__name__)

_REQUIRED_TEMPORAL = ("TEMPORAL_HOST", "TEMPORAL_NAMESPACE", "TEMPORAL_API_KEY")
_REQUIRED_CLICKHOUSE = (
    "CLICKHOUSE_HOST",
    "CLICKHOUSE_PORT",
    "CLICKHOUSE_USER",
    "CLICKHOUSE_PASSWORD",
    "CLICKHOUSE_DATABASE",
)


def _env_presence() -> dict[str, Any]:
    temporal = {key: bool((os.environ.get(key) or "").strip()) for key in _REQUIRED_TEMPORAL}
    clickhouse = {key: bool((os.environ.get(key) or "").strip()) for key in _REQUIRED_CLICKHOUSE}
    return {
        "temporal": temporal,
        "clickhouse": clickhouse,
        "temporal_complete": all(temporal.values()),
        "clickhouse_complete": all(clickhouse.values()),
    }


async def check_temporal_connection() -> dict[str, Any]:
    if not temporal_configured():
        return {"configured": False, "ok": False, "error": "TEMPORAL_HOST unset"}
    try:
        client = await get_temporal_client()
        namespace = os.environ.get("TEMPORAL_NAMESPACE", "default")
        return {
            "configured": True,
            "ok": True,
            "namespace": namespace,
            "workflows": registered_workflow_names(),
            "client_connected": client is not None,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("temporal_health_check_failed error=%s", exc)
        return {"configured": True, "ok": False, "error": str(exc)}


_CLICKHOUSE_SCHEMA_SQL = """
CREATE DATABASE IF NOT EXISTS gravitre;

CREATE TABLE IF NOT EXISTS gravitre.pipeline_events (
  org_id UUID,
  message_id UUID,
  stage_name LowCardinality(String),
  tier LowCardinality(String),
  duration_ms UInt32,
  cache_hit Bool,
  model_used LowCardinality(String),
  cost_usd Float32,
  created_at DateTime64(3, 'UTC')
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (org_id, created_at, stage_name);

CREATE TABLE IF NOT EXISTS gravitre.outcome_events (
  org_id UUID,
  agent_id UUID,
  workflow_run_id UUID,
  action_type LowCardinality(String),
  metric_name LowCardinality(String),
  metric_before Float64,
  metric_after Float64,
  delta Float64,
  attribution_window_days UInt8,
  created_at DateTime64(3, 'UTC')
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (org_id, created_at, metric_name);

CREATE TABLE IF NOT EXISTS gravitre.mcp_executions (
  org_id UUID,
  tool_id UUID,
  capability_tier LowCardinality(String),
  status LowCardinality(String),
  latency_ms UInt32,
  created_at DateTime64(3, 'UTC')
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (org_id, created_at);
"""


def _clickhouse_schema_statements() -> list[str]:
    schema_path = Path(__file__).resolve().parents[3] / "scripts" / "clickhouse_schema.sql"
    raw = _CLICKHOUSE_SCHEMA_SQL
    if schema_path.is_file():
        raw = schema_path.read_text(encoding="utf-8")
    return [part.strip() for part in raw.split(";") if part.strip()]


def apply_clickhouse_schema() -> dict[str, Any]:
    ch = get_clickhouse_service()
    if not ch.is_available():
        return {"ok": False, "error": "CLICKHOUSE_HOST unset"}
    client = ch._client  # noqa: SLF001 — internal health/activation path
    applied: list[str] = []
    for statement in _clickhouse_schema_statements():
        client.command(statement)
        applied.append(statement.split("\n", 1)[0][:80])
    return {"ok": True, "statements_applied": len(applied)}


async def check_clickhouse_connection(*, apply_schema: bool = False) -> dict[str, Any]:
    try:
        ch = get_clickhouse_service()
    except Exception as exc:  # noqa: BLE001
        return {"configured": True, "ok": False, "error": f"client_init_failed: {exc}"}
    if not ch.is_available():
        return {
            "configured": bool((os.getenv("CLICKHOUSE_HOST") or "").strip()),
            "ok": False,
            "error": "ClickHouse client unavailable (check CLICKHOUSE_PASSWORD / CLICKHOUSE_SECRET_KEY)",
        }
    if apply_schema:
        try:
            apply_clickhouse_schema()
        except Exception as exc:  # noqa: BLE001
            return {"configured": True, "ok": False, "error": f"schema_apply_failed: {exc}"}
    try:
        rows = await ch.query("SHOW TABLES FROM gravitre")
        table_names = sorted(str(row.get("name") or list(row.values())[0]) for row in rows)
        expected = {"pipeline_events", "outcome_events", "mcp_executions"}
        missing = sorted(expected - set(table_names))
        recent = await ch.query(
            """
            SELECT stage_name, duration_ms, created_at
            FROM gravitre.pipeline_events
            ORDER BY created_at DESC
            LIMIT 5
            """
        )
        return {
            "configured": True,
            "ok": not missing,
            "tables": table_names,
            "missing_tables": missing,
            "recent_pipeline_events": len(recent),
            "sample_events": recent[:3],
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("clickhouse_health_check_failed error=%s", exc)
        return {"configured": True, "ok": False, "error": str(exc)}


async def get_infrastructure_health(*, apply_clickhouse_schema: bool = False) -> dict[str, Any]:
    env = _env_presence()
    temporal = await check_temporal_connection()
    clickhouse = await check_clickhouse_connection(apply_schema=apply_clickhouse_schema)
    return {
        "environment": env,
        "temporal": temporal,
        "clickhouse": clickhouse,
        "ok": bool(temporal.get("ok")) and bool(clickhouse.get("ok")),
    }
