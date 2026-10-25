"""Read-only business-wide sensitivity policy.

These settings adjust optional evidence inclusion and proactive hints, never execution
permissions, consent, security gates, or source access.
"""
from __future__ import annotations

from typing import Any

VALID = frozenset({"conservative", "balanced", "proactive"})
CAPABILITIES = ("contextual", "sentiment", "causal", "temporal", "relational", "adaptive", "predictive")


def normalize_policy(raw: Any) -> dict[str, str]:
    stored = raw if isinstance(raw, dict) else {}
    return {name: (
        str((stored.get(name) or {}).get("mode"))
        if isinstance(stored.get(name), dict) and (stored.get(name) or {}).get("mode") in VALID
        else "balanced"
    ) for name in CAPABILITIES}


def include_optional_evidence(capability: str, mode: str, classification: dict[str, Any]) -> bool:
    """Conservative requires an explicit relevant classification; proactive permits
    optional retrieval where a matching concrete entity/department is available."""
    if capability == "causal":
        return bool(classification.get("requires_causal"))
    if capability == "predictive":
        return bool(classification.get("requires_prediction"))
    if capability == "relational":
        return bool(classification.get("requires_graph"))
    if capability == "adaptive":
        return bool(classification.get("department")) or mode == "proactive"
    return True


def load_overview_policy(org_id: str, settings: Any) -> dict[str, str]:
    from app.workflows.repository import get_supabase_client

    # Fail with normal defaults when the feature is not migrated yet.
    # Never bypass an approval check as a result of missing policy data.
    try:
        res = (get_supabase_client(settings).table("intelligence_overview_profiles")
               .select("capabilities").eq("org_id", org_id).limit(1).execute())
        return normalize_policy((res.data or [{}])[0].get("capabilities"))
    except Exception:
        return normalize_policy({})
