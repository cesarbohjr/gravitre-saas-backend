"""Phase 2C source data governance: who may persist customer context, and for how long.

Stored in ``organizations.settings.sourceDataGovernance`` (same pattern as
``memoryEntityEmbeddings``). Default is the safe state: no customer context is
persisted from any source and nothing is pruned.

* ``customerContext``: opt-in for the new customer-context paths (entity writer,
  customer observations, background indexing pilot). ``connectors`` empty means
  every connected source once enabled; otherwise an allowlist of vendors.
  Explicitly configured knowledge syncs (Notion pages, HubSpot notes and so on)
  are unchanged: choosing sync targets is already the opt-in for those.
* ``retentionDays``: per-vendor maximum age of indexed documents, enforced by the
  retention prune job (KNOWLEDGE_RETENTION_PRUNE_ENABLED). Missing means keep.
"""
from __future__ import annotations

from typing import Any

SETTINGS_KEY = "sourceDataGovernance"
MIN_RETENTION_DAYS = 7
MAX_RETENTION_DAYS = 3650

DEFAULT_POLICY: dict[str, Any] = {
    "customerContext": {"enabled": False, "connectors": []},
    "retentionDays": {},
}


def _vendor(value: Any) -> str:
    return str(value or "").strip().lower()


def normalize_source_governance(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {}
    cc = raw.get("customerContext") if isinstance(raw.get("customerContext"), dict) else {}
    connectors = sorted({_vendor(v) for v in (cc.get("connectors") or []) if _vendor(v)})
    retention: dict[str, int] = {}
    raw_ret = raw.get("retentionDays") if isinstance(raw.get("retentionDays"), dict) else {}
    for vendor, days in raw_ret.items():
        v = _vendor(vendor)
        try:
            n = int(days)
        except (TypeError, ValueError):
            continue
        if v and n > 0:
            retention[v] = max(MIN_RETENTION_DAYS, min(MAX_RETENTION_DAYS, n))
    return {
        "customerContext": {"enabled": cc.get("enabled") is True, "connectors": connectors},
        "retentionDays": retention,
    }


def _org_settings(client: Any, org_id: str) -> dict[str, Any]:
    row = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute()
    data = (row.data or [{}])[0].get("settings") if row.data else {}
    return data if isinstance(data, dict) else {}


def load_source_governance(client: Any, org_id: str) -> dict[str, Any]:
    raw = _org_settings(client, org_id).get(SETTINGS_KEY)
    return normalize_source_governance(raw if isinstance(raw, dict) else None)


def save_source_governance(client: Any, org_id: str, policy: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_source_governance(policy)
    settings = {**_org_settings(client, org_id), SETTINGS_KEY: normalized}
    client.table("organizations").update({"settings": settings}).eq("id", org_id).execute()
    return normalized


def customer_context_allowed(policy: dict[str, Any] | None, vendor: str | None) -> bool:
    """True only when the org opted in and ``vendor`` is covered by the allowlist."""
    normalized = normalize_source_governance(policy)
    cc = normalized["customerContext"]
    if not cc["enabled"]:
        return False
    v = _vendor(vendor)
    if not v:
        return False
    return not cc["connectors"] or v in cc["connectors"]


def customer_context_allowed_for_org(client: Any, org_id: str, vendor: str | None) -> bool:
    """Fail closed: any error reading the policy means not allowed."""
    try:
        return customer_context_allowed(load_source_governance(client, org_id), vendor)
    except Exception:  # noqa: BLE001
        return False


def retention_days_for(policy: dict[str, Any] | None, vendor: str | None) -> int | None:
    return normalize_source_governance(policy)["retentionDays"].get(_vendor(vendor))
