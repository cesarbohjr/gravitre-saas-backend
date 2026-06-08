"""Connector fixtures for workflow digital-twin simulation (STA-120)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class ConnectorFixtureError(Exception):
    code = "FIXTURE_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


def _serialize(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "orgId": str(row["org_id"]),
        "environment": row.get("environment") or "production",
        "connectorType": row["connector_type"],
        "action": row["action"],
        "label": row.get("label"),
        "requestFingerprint": row.get("request_fingerprint") or {},
        "response": row.get("response") or {},
        "sourceRunId": str(row["source_run_id"]) if row.get("source_run_id") else None,
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
    }


def list_connector_fixtures(
    client: Any,
    org_id: str,
    *,
    environment: str | None = None,
    connector_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    query = (
        client.table("connector_fixtures")
        .select("*")
        .eq("org_id", org_id)
        .order("updated_at", desc=True)
        .limit(limit)
    )
    if environment:
        query = query.eq("environment", environment)
    if connector_type:
        query = query.eq("connector_type", connector_type)
    result = query.execute()
    return [_serialize(dict(row)) for row in (result.data or [])]


def get_connector_fixture(client: Any, org_id: str, fixture_id: str) -> dict[str, Any]:
    result = (
        client.table("connector_fixtures")
        .select("*")
        .eq("id", fixture_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise ConnectorFixtureError("Fixture not found", code="NOT_FOUND")
    return _serialize(dict(result.data[0]))


def upsert_connector_fixture(
    client: Any,
    *,
    org_id: str,
    connector_type: str,
    action: str,
    response: dict[str, Any],
    actor_id: str,
    environment: str = "production",
    label: str | None = None,
    request_fingerprint: dict[str, Any] | None = None,
    source_run_id: str | None = None,
) -> dict[str, Any]:
    if not connector_type.strip() or not action.strip():
        raise ConnectorFixtureError("connectorType and action are required", code="VALIDATION_ERROR")
    if not response:
        raise ConnectorFixtureError("response payload is required", code="VALIDATION_ERROR")

    now = datetime.now(timezone.utc).isoformat()
    existing = (
        client.table("connector_fixtures")
        .select("*")
        .eq("org_id", org_id)
        .eq("environment", environment)
        .eq("connector_type", connector_type.strip())
        .eq("action", action.strip())
        .limit(20)
        .execute()
    )
    row = None
    for candidate in existing.data or []:
        if label is None or str(candidate.get("label") or "") == label:
            row = dict(candidate)
            break

    payload = {
        "org_id": org_id,
        "environment": environment,
        "connector_type": connector_type.strip(),
        "action": action.strip(),
        "label": label,
        "request_fingerprint": request_fingerprint or {},
        "response": response,
        "source_run_id": source_run_id,
        "updated_at": now,
    }
    if row:
        updated = client.table("connector_fixtures").update(payload).eq("id", row["id"]).execute()
        return _serialize(dict((updated.data or [row])[0]))

    payload["created_by"] = actor_id
    payload["created_at"] = now
    inserted = client.table("connector_fixtures").insert(payload).execute()
    if not inserted.data:
        raise RuntimeError("connector_fixtures insert returned no row")
    return _serialize(dict(inserted.data[0]))


def lookup_connector_fixture(
    client: Any,
    *,
    org_id: str,
    connector_type: str,
    action: str,
    environment: str = "production",
) -> dict[str, Any] | None:
    result = (
        client.table("connector_fixtures")
        .select("*")
        .eq("org_id", org_id)
        .eq("environment", environment)
        .eq("connector_type", connector_type)
        .eq("action", action)
        .order("updated_at", desc=True)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return dict(result.data[0])


def delete_connector_fixture(client: Any, org_id: str, fixture_id: str) -> None:
    result = (
        client.table("connector_fixtures")
        .delete()
        .eq("id", fixture_id)
        .eq("org_id", org_id)
        .execute()
    )
    if not result.data:
        raise ConnectorFixtureError("Fixture not found", code="NOT_FOUND")
