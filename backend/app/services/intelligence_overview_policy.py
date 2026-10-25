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


def apply_response_sensitivity(result: dict[str, Any], policy: dict[str, str]) -> dict[str, Any]:
    """Control optional capability evidence verbosity without touching execution.

    All seven modes are represented in the response. Conservative suppresses
    unverified/optional capability evidence, balanced leaves the router result
    unchanged, proactive preserves extra available evidence. This does not
    modify the underlying model's inference thresholds or permissions.
    """
    output = dict(result)
    enrichments = output.get("enrichments")
    if not isinstance(enrichments, dict):
        return output
    new_enrichments = dict(enrichments)
    capabilities = new_enrichments.get("capabilities")
    if not isinstance(capabilities, dict):
        return output
    adjusted = {}
    for name in CAPABILITIES:
        slot = capabilities.get(name)
        if not isinstance(slot, dict):
            continue
        mode = policy.get(name, "balanced")
        item = dict(slot)
        item["sensitivity_mode"] = mode
        item["runtime_effect"] = "optional_evidence_presentation"
        if mode == "conservative" and item.get("status") not in {"available", "ok"}:
            # Do not expose weak speculative detail as established intelligence.
            item.pop("data", None)
            item["evidence_suppressed"] = True
        adjusted[name] = item
    new_enrichments["capabilities"] = {**capabilities, **adjusted}
    output["enrichments"] = new_enrichments
    return output
