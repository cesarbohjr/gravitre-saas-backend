"""Org metric definitions SoT helpers for CognitiveTurnKernel Phase 5.

Platform defaults (Cesar-authorized Gravitre standard formulas — not SKU prices):
- MQL, CAC, ARR. Org rows in org_metric_definitions win over defaults.
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.core.logging import get_logger

logger = get_logger(__name__)

# Cesar-authorized platform default formulas (2026-08 Part 1 item 3).
# These are definition text only — not billable SKUs or Enable toggles.
PLATFORM_METRIC_DEFAULTS: dict[str, dict[str, Any]] = {
    "mql": {
        "metric_key": "mql",
        "label": "Marketing Qualified Leads",
        "formula": "count(leads where marketing_qualified=true)",
        "source_system": "crm",
        "owner": "platform",
    },
    "cac": {
        "metric_key": "cac",
        "label": "Customer Acquisition Cost",
        "formula": "(sales_spend + marketing_spend) / new_customers",
        "source_system": "finance",
        "owner": "platform",
    },
    "arr": {
        "metric_key": "arr",
        "label": "Annual Recurring Revenue",
        "formula": "sum(mrr) * 12",
        "source_system": "billing",
        "owner": "platform",
    },
}


def list_platform_defaults() -> list[dict[str, Any]]:
    """Return Cesar-authorized platform default metric definitions."""
    return [dict(v) for v in PLATFORM_METRIC_DEFAULTS.values()]


def get_platform_default(metric_key: str) -> dict[str, Any] | None:
    key = (metric_key or "").strip().lower()
    row = PLATFORM_METRIC_DEFAULTS.get(key)
    return dict(row) if row else None


def list_metric_definitions(
    client: Any,
    org_id: str,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """List org-scoped metric definition overrides. Always filters by org_id."""
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


def list_metrics_with_defaults(
    client: Any,
    org_id: str,
    *,
    limit: int = 100,
) -> dict[str, Any]:
    """Admin list: platform defaults + org overrides (org row wins when resolving)."""
    overrides = list_metric_definitions(client, org_id, limit=limit)
    override_keys = {
        str(r.get("metric_key") or "").strip().lower()
        for r in overrides
        if isinstance(r, dict)
    }
    defaults = list_platform_defaults()
    return {
        "defaults": defaults,
        "overrides": overrides,
        "definitions": overrides,
        "default_keys_without_override": [
            d["metric_key"] for d in defaults if d["metric_key"] not in override_keys
        ],
        "orgId": org_id,
    }


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


def resolve_metric(
    client: Any,
    org_id: str,
    metric_key: str,
    *,
    agent_id: str | None = None,
    fallback_label: str | None = None,
) -> dict[str, Any]:
    """
    Resolve a metric: org override if present, else platform default, else label fallback.
    """
    _ = agent_id
    key = (metric_key or "").strip()
    key_l = key.lower()
    definition = get_metric_definition(client, org_id, key)
    if definition is None and key_l != key:
        definition = get_metric_definition(client, org_id, key_l)
    if definition:
        return {
            "metric_key": definition.get("metric_key") or key_l or key,
            "definition_id": definition.get("id"),
            "label": definition.get("label") or key,
            "formula": definition.get("formula"),
            "source_system": definition.get("source_system"),
            "owner": definition.get("owner"),
            "resolved_from": "org_metric_definitions",
            "org_id": org_id,
        }
    platform = get_platform_default(key_l or key)
    if platform:
        return {
            "metric_key": platform["metric_key"],
            "definition_id": None,
            "label": platform.get("label") or key,
            "formula": platform.get("formula"),
            "source_system": platform.get("source_system"),
            "owner": platform.get("owner"),
            "resolved_from": "platform_default",
            "org_id": org_id,
        }
    return {
        "metric_key": key_l or key,
        "definition_id": None,
        "label": fallback_label or key,
        "formula": None,
        "source_system": None,
        "owner": None,
        "resolved_from": "fallback_label",
        "org_id": org_id,
    }


def resolve_metric_for_agent(
    client: Any,
    org_id: str,
    metric_key: str,
    *,
    agent_id: str | None = None,
    fallback_label: str | None = None,
) -> dict[str, Any]:
    """Alias kept for call sites; prefer ``resolve_metric``."""
    return resolve_metric(
        client,
        org_id,
        metric_key,
        agent_id=agent_id,
        fallback_label=fallback_label,
    )


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
    """Insert or update an org metric definition override. Always scoped by org_id."""
    if not org_id or not metric_key or client is None:
        return None
    key = metric_key.strip().lower()
    existing = get_metric_definition(client, org_id, key) or get_metric_definition(
        client, org_id, metric_key.strip()
    )
    platform = get_platform_default(key)
    payload: dict[str, Any] = {
        "org_id": org_id,
        "metric_key": key,
        "label": label or (platform or {}).get("label") or key,
        "formula": formula if formula is not None else (platform or {}).get("formula"),
        "source_system": source_system
        if source_system is not None
        else (platform or {}).get("source_system"),
        "owner": owner if owner is not None else (platform or {}).get("owner"),
    }
    try:
        if existing and existing.get("id"):
            updated = (
                client.table("org_metric_definitions")
                .update(
                    {
                        "label": payload["label"],
                        "formula": payload["formula"],
                        "source_system": payload["source_system"],
                        "owner": payload["owner"],
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
