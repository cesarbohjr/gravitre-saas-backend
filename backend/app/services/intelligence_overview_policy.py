"""Read-only business-wide sensitivity policy.

These settings adjust optional evidence inclusion and proactive hints, never execution
permissions, consent, security gates, or source access.
"""
from __future__ import annotations

from typing import Any

VALID = frozenset({"conservative", "balanced", "proactive"})
CAPABILITIES = ("contextual", "sentiment", "causal", "temporal", "relational", "adaptive", "predictive")
# Abilities an admin may turn off: without them answers get less rich, never wrong
# or unsafe. Context, time and relationships always stay on.
CAN_TURN_OFF = frozenset({"sentiment", "causal", "predictive", "adaptive"})
OFF = "off"


def normalize_policy(raw: Any) -> dict[str, str]:
    """Mode per ability; ``"off"`` when an admin turned a safe ability off."""
    stored = raw if isinstance(raw, dict) else {}
    policy: dict[str, str] = {}
    for name in CAPABILITIES:
        slot = stored.get(name) if isinstance(stored.get(name), dict) else {}
        if name in CAN_TURN_OFF and slot.get("enabled") is False:
            policy[name] = OFF
        else:
            policy[name] = str(slot.get("mode")) if slot.get("mode") in VALID else "balanced"
    return policy


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
        if mode == OFF:
            item.pop("data", None)
            item["evidence_suppressed"] = True
            item["suppression_reason"] = "turned_off"
            adjusted[name] = item
            continue
        item["runtime_effect"] = "optional_enrichment_eligibility_and_evidence_threshold"
        minimum = evidence_threshold(name, mode)
        item["surfacing_threshold"] = minimum
        evidence_confidence = item.get("confidence")
        if isinstance(evidence_confidence, (int, float)) and not isinstance(evidence_confidence, bool) and evidence_confidence < minimum:
            item.pop("data", None)
            item["evidence_suppressed"] = True
            item["suppression_reason"] = "below_surfacing_threshold"
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
    An ability an admin turned off does no work at all.
    """
    deferred = context.get("defer_optional") is True
    department = bool(classification.get("department"))
    entity = bool(classification.get("entity_type") and classification.get("entity_id"))
    requested = {
        "causal": bool(classification.get("requires_causal")),
        "predictive": bool(classification.get("requires_prediction")),
        "relational": bool(classification.get("requires_graph")),
        "adaptive": department or bool(context.get("retrieval_plan")) or bool(context.get("catalog_model_inputs")) or any(bool(classification.get(key)) for key in ("requires_prediction", "requires_causal", "requires_graph")),
    }
    eligible = {
        "causal": not deferred and requested["causal"],
        "predictive": not deferred and (
            requested["predictive"] or (policy.get("predictive") == "proactive" and
                                        department and bool(classification.get("metric")))),
        "relational": not deferred and (
            requested["relational"] or (policy.get("relational") == "proactive" and entity)),
        "adaptive": not deferred and (
            requested["adaptive"] or (policy.get("adaptive") == "proactive"
                                      and bool(context.get("understanding")))),
    }
    return {name: on and policy.get(name) != OFF for name, on in eligible.items()}


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
