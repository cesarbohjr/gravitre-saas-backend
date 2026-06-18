"""Per-asset adoption events for unified marketplace installs (MKT-AUDIT-10.2)."""
from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from app.workflows.constants import RUN_STATUS_COMPLETED

logger = logging.getLogger(__name__)

_ADOPTION_EVENT_TYPES = frozenset({"agent_run", "workflow_run", "view"})
_ENTITY_TYPES = frozenset({"agent", "workflow"})


def _entity_list_key(entity_type: str) -> str:
    return "agentIds" if entity_type == "agent" else "workflowIds"


def find_active_installs_for_entity(
    client: Any,
    org_id: str,
    *,
    entity_type: str,
    entity_id: str,
) -> list[dict[str, Any]]:
    """Match marketplace installs whose metadata references the given agent/workflow."""
    if entity_type not in _ENTITY_TYPES:
        return []

    entity_id_str = str(entity_id)
    list_key = _entity_list_key(entity_type)
    result = (
        client.table("marketplace_installs")
        .select("id, asset_id, metadata, installed_entity_type, installed_entity_id")
        .eq("org_id", org_id)
        .eq("status", "active")
        .execute()
    )
    matches: list[dict[str, Any]] = []
    for row in result.data or []:
        metadata = row.get("metadata") or {}
        listed_ids = {str(value) for value in (metadata.get(list_key) or [])}
        if entity_id_str in listed_ids:
            matches.append(dict(row))
            continue
        if (
            str(row.get("installed_entity_type") or "") == entity_type
            and str(row.get("installed_entity_id") or "") == entity_id_str
        ):
            matches.append(dict(row))
    return matches


def record_marketplace_adoption_event(
    client: Any,
    *,
    org_id: str,
    asset_id: str,
    install_id: str | None,
    event_type: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    source_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    idempotency_key: str,
) -> dict[str, Any] | None:
    """Insert a unified asset adoption event. Returns row or None on duplicate."""
    if event_type not in _ADOPTION_EVENT_TYPES:
        raise ValueError(f"invalid event_type: {event_type}")
    if entity_type is not None and entity_type not in _ENTITY_TYPES:
        raise ValueError(f"invalid entity_type: {entity_type}")

    row = {
        "org_id": org_id,
        "asset_id": asset_id,
        "install_id": install_id,
        "event_type": event_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "source_id": source_id,
        "metadata": metadata or {},
        "idempotency_key": idempotency_key,
    }
    try:
        inserted = client.table("marketplace_asset_adoption_events").insert(row).execute()
    except Exception as exc:  # noqa: BLE001
        message = str(exc).lower()
        if "duplicate" in message or "unique" in message or "23505" in message:
            return None
        raise
    if not inserted.data:
        return None
    return dict(inserted.data[0])


def record_adoption_for_agent_run(
    client: Any,
    *,
    org_id: str,
    agent_id: str,
    job_id: str,
) -> list[dict[str, Any]]:
    installs = find_active_installs_for_entity(
        client,
        org_id,
        entity_type="agent",
        entity_id=agent_id,
    )
    recorded: list[dict[str, Any]] = []
    for install in installs:
        row = record_marketplace_adoption_event(
            client,
            org_id=org_id,
            asset_id=str(install["asset_id"]),
            install_id=str(install["id"]),
            event_type="agent_run",
            entity_type="agent",
            entity_id=agent_id,
            source_id=job_id,
            idempotency_key=f"agent_run:{job_id}:{install['asset_id']}",
        )
        if row:
            recorded.append(row)
    return recorded


def record_adoption_for_workflow_run(
    client: Any,
    *,
    org_id: str,
    workflow_id: str,
    run_id: str,
    final_status: str,
) -> list[dict[str, Any]]:
    if final_status != RUN_STATUS_COMPLETED:
        return []

    installs = find_active_installs_for_entity(
        client,
        org_id,
        entity_type="workflow",
        entity_id=workflow_id,
    )
    recorded: list[dict[str, Any]] = []
    for install in installs:
        row = record_marketplace_adoption_event(
            client,
            org_id=org_id,
            asset_id=str(install["asset_id"]),
            install_id=str(install["id"]),
            event_type="workflow_run",
            entity_type="workflow",
            entity_id=workflow_id,
            source_id=run_id,
            idempotency_key=f"workflow_run:{run_id}:{install['asset_id']}",
        )
        if row:
            recorded.append(row)
    return recorded


def maybe_record_workflow_adoption(
    client: Any,
    *,
    org_id: str,
    run_id: str,
    final_status: str,
) -> None:
    """Best-effort adoption ingest after workflow completion."""
    if final_status != RUN_STATUS_COMPLETED:
        return
    try:
        run_row = (
            client.table("workflow_runs")
            .select("workflow_id")
            .eq("id", run_id)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
        )
        if not run_row.data:
            return
        workflow_id = str(run_row.data[0].get("workflow_id") or "")
        if not workflow_id:
            return
        record_adoption_for_workflow_run(
            client,
            org_id=org_id,
            workflow_id=workflow_id,
            run_id=run_id,
            final_status=final_status,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "marketplace_adoption_workflow skipped org_id=%s run_id=%s error=%s",
            org_id,
            run_id,
            str(exc),
        )


def maybe_record_agent_adoption(client: Any, job: dict[str, Any]) -> None:
    """Best-effort adoption ingest after agent job completion."""
    payload = job.get("payload") or {}
    agent_id = str(payload.get("agent_id") or payload.get("agentId") or "")
    org_id = str(job.get("org_id") or "")
    job_id = str(job.get("id") or "")
    if not agent_id or not org_id or not job_id:
        return
    try:
        record_adoption_for_agent_run(
            client,
            org_id=org_id,
            agent_id=agent_id,
            job_id=job_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "marketplace_adoption_agent skipped org_id=%s job_id=%s error=%s",
            org_id,
            job_id,
            str(exc),
        )


def top_assets_by_adoption(
    client: Any,
    org_id: str,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 25))
    result = (
        client.table("marketplace_asset_adoption_events")
        .select("asset_id, marketplace_assets(slug, title)")
        .eq("org_id", org_id)
        .execute()
    )
    counts: Counter[str] = Counter()
    meta: dict[str, dict[str, Any]] = {}
    for row in result.data or []:
        asset_id = str(row.get("asset_id") or "")
        if not asset_id:
            continue
        counts[asset_id] += 1
        asset = row.get("marketplace_assets") or {}
        meta[asset_id] = {
            "slug": asset.get("slug"),
            "title": asset.get("title"),
        }
    ranked = counts.most_common(limit)
    return [
        {
            "assetId": asset_id,
            "slug": meta.get(asset_id, {}).get("slug"),
            "title": meta.get(asset_id, {}).get("title"),
            "usageEvents": count,
        }
        for asset_id, count in ranked
    ]


def count_adoption_events(client: Any, org_id: str) -> int:
    result = (
        client.table("marketplace_asset_adoption_events")
        .select("id", count="exact")
        .eq("org_id", org_id)
        .execute()
    )
    total = getattr(result, "count", None)
    if total is not None:
        return int(total)
    return len(result.data or [])
