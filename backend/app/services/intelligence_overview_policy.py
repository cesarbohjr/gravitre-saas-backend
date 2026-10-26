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


def select_enrichment_work(
    classification: dict[str, Any],
    context: dict[str, Any],
    policy: dict[str, str],
) -> dict[str, bool]:
    """Per-capability thresholds for OPTIONAL router intelligence work.

    Explicit user intent is always eligible, irrespective of sensitivity mode.
    Proactive mode expands candidate work only when relevant *authorized*
    classification evidence exists. No mode changes permissions or write gates.
    """
    deferred = context.get("defer_optional") is True
    department = bool(classification.get("department"))
    entity = bool(classification.get("entity_type") and classification.get("entity_id"))
    requested = {
        "causal": bool(classification.get("requires_causal")),
        "predictive": bool(classification.get("requires_prediction")),
        "relational": bool(classification.get("requires_graph")),
        "adaptive": department,
    }
    return {
        "causal": not deferred and requested["causal"],
        "predictive": not deferred and (
            requested["predictive"] or (policy.get("predictive") == "proactive" and
                                        department and bool(classification.get("metric")))),
        "relational": not deferred and (
            requested["relational"] or (policy.get("relational") == "proactive" and entity)),
        "adaptive": not deferred and (
            department or (policy.get("adaptive") == "proactive"
                           and bool(context.get("retrieval_plan")))),
    }


def evidence_threshold(capability: str, mode: str) -> float:
    """Default recommendation surfacing threshold. Never an execution threshold."""
    defaults = {
        "contextual": (0.85, 0.65, 0.45),
        "sentiment": (0.85, 0.65, 0.45),
        "causal": (0.95, 0.80, 0.70),
        "temporal": (0.90, 0.70, 0.50),
        "relational": (0.90, 0.70, 0.50),
        "adaptive": (0.90, 0.70, 0.50),
        "predictive": (0.95, 0.80, 0.65),
    }
    level = {"conservative": 0, "balanced": 1, "proactive": 2}.get(mode, 1)
    return defaults[capability][level]
