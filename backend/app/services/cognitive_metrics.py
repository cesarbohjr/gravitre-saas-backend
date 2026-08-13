"""Org metric definitions SoT helpers for CognitiveTurnKernel Phase 5."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.core.logging import get_logger

logger = get_logger(__name__)


def list_metric_definitions(
    client: Any,
    org_id: str,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """List org-scoped metric definitions. Always filters by org_id."""
    if not org_id or client is None:
        return []
    try:
        rows = (
            client.table("org_metric_definitions")
            .select("id, org_id, metric_key, label, formula, source_system, owner, created_at")
            .eq("org_id", org_id)
            .order("metric_key")
            .limit(max(1, min(int(limit), 500)))
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("cognitive_metrics_list_skipped error=%s", exc)
        return []
    return [r for r in rows if isinstance(r, dict)]


def get_metric_definition(
    client: Any,
    org_id: str,
    metric_key: str,
) -> dict[str, Any] | None:
    """Load a single org-scoped metric definition. Always filters by org_id."""
    if not org_id or not metric_key or client is None:
        return None
    try:
        rows = (
            client.table("org_metric_definitions")
            .select("id, org_id, metric_key, label, formula, source_system, owner, created_at")
            .eq("org_id", org_id)
            .eq("metric_key", metric_key)
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("cognitive_metrics_get_skipped error=%s", exc)
        return None
    if not rows:
        return None
    row = rows[0]
    return row if isinstance(row, dict) else None


def resolve_metric_for_agent(
    client: Any,
    org_id: str,
    metric_key: str,
    *,
    agent_id: str | None = None,
    fallback_label: str | None = None,
) -> dict[str, Any]:
    """
    Resolve a metric for agent use. Prefer org definition when present so two
    agents share the same metric_definition id.
    """
    _ = agent_id
    definition = get_metric_definition(client, org_id, metric_key)
    if definition:
        return {
            "metric_key": metric_key,
            "definition_id": definition.get("id"),
            "label": definition.get("label") or metric_key,
            "formula": definition.get("formula"),
            "source_system": definition.get("source_system"),
            "owner": definition.get("owner"),
            "resolved_from": "org_metric_definitions",
            "org_id": org_id,
        }
    return {
        "metric_key": metric_key,
        "definition_id": None,
        "label": fallback_label or metric_key,
        "formula": None,
        "source_system": None,
        "owner": None,
        "resolved_from": "fallback_label",
        "org_id": org_id,
    }


def upsert_metric_definition(
    client: Any,
    org_id: str,
    metric_key: str,
    *,
    label: str | None = None,
    formula: str | None = None,
    source_system: str | None = None,
    owner: str | None = None,
) -> dict[str, Any] | None:
    """Insert or update an org metric definition. Always scoped by org_id."""
    if not org_id or not metric_key or client is None:
        return None
    existing = get_metric_definition(client, org_id, metric_key)
    payload: dict[str, Any] = {
        "org_id": org_id,
        "metric_key": metric_key,
        "label": label or metric_key,
        "formula": formula,
        "source_system": source_system,
        "owner": owner,
    }
    try:
        if existing and existing.get("id"):
            updated = (
                client.table("org_metric_definitions")
                .update(
                    {
                        "label": payload["label"],
                        "formula": formula,
                        "source_system": source_system,
                        "owner": owner,
                    }
                )
                .eq("id", existing["id"])
                .eq("org_id", org_id)
                .execute()
                .data
            )
            if updated:
                return updated[0] if isinstance(updated[0], dict) else existing
            return existing
        payload["id"] = str(uuid4())
        inserted = client.table("org_metric_definitions").insert(payload).execute().data
        if inserted:
            return inserted[0] if isinstance(inserted[0], dict) else payload
        return payload
    except Exception as exc:  # noqa: BLE001
        logger.debug("cognitive_metrics_upsert_skipped error=%s", exc)
        return None
