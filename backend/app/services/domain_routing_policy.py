"""Domain-aware routing policy — extends existing selectors, not a parallel router."""
from __future__ import annotations

from typing import Any

from app.domain.loader import load_domain_profile
from app.services.domain_intelligence_service import DOMAIN_CONFIDENCE_THRESHOLD
from app.services.learning_strategy_keys import domain_segment_active
from app.core.safe_dict import safe_normalize_stored_dict

LLM_TIER_ORDER = ("fast", "standard", "reasoning")


def is_domain_routing_active(classification: dict[str, Any] | None) -> bool:
    domain = (classification or {}).get("domain") or {}
    if domain.get("routing_active") is False:
        return False
    if domain.get("routing_active") is True:
        return True
    return float(domain.get("confidence") or 0) >= DOMAIN_CONFIDENCE_THRESHOLD


def get_domain_profile(classification: dict[str, Any] | None) -> dict[str, Any] | None:
    if not is_domain_routing_active(classification):
        return None
    domain = (classification or {}).get("domain") or {}
    profile_id = domain.get("profile_id") or domain.get("department_key") or domain.get("department")
    if not profile_id:
        return None
    profile_key = str(profile_id).lower().replace(" ", "_")
    return load_domain_profile(profile_key)


def build_routing_metadata(classification: dict[str, Any] | None) -> dict[str, Any]:
    domain = (classification or {}).get("domain") or {}
    profile = get_domain_profile(classification)
    return {
        "domain_routing_active": is_domain_routing_active(classification),
        "domain_confidence": float(domain.get("confidence") or 0),
        "domain_source": domain.get("source"),
        "profile_id": (profile or {}).get("profile_id") or domain.get("profile_id"),
        "segment_key_format": "domain_v2" if domain_segment_active(classification) else "legacy",
    }


def apply_model_selection_policy(
    selection: dict[str, Any],
    classification: dict[str, Any],
) -> dict[str, Any]:
    if not is_domain_routing_active(classification):
        return selection
    profile = get_domain_profile(classification)
    if not profile:
        return selection
    updated = dict(selection)
    risk = str(profile.get("risk_tolerance") or "medium").lower()
    current_tier = str(updated.get("llm_tier") or "standard")
    if risk == "low" and current_tier == "fast":
        updated["llm_tier"] = "standard"
        updated["domain_routing_applied"] = True
        updated["domain_routing_reason"] = f"{profile.get('label')} profile prefers conservative model tier"
    elif risk == "low" and current_tier == "standard":
        domain = classification.get("domain") or {}
        if domain.get("execution_type") == "action":
            updated["llm_tier"] = "reasoning"
            updated["domain_routing_applied"] = True
            updated["domain_routing_reason"] = "Low-risk domain with action execution — reasoning tier"
    updated["domain_profile_id"] = profile.get("profile_id")
    return updated


def apply_agent_selection_policy(
    agent_selection: dict[str, Any],
    classification: dict[str, Any],
) -> dict[str, Any]:
    if not is_domain_routing_active(classification):
        return agent_selection
    profile = get_domain_profile(classification)
    if not profile:
        return agent_selection
    updated = dict(agent_selection)
    preferred = [str(item).lower() for item in (profile.get("connector_preferences") or [])]
    persona = safe_normalize_stored_dict(updated, key="persona")
    existing = [str(item).lower() for item in (persona.get("preferred_connectors") or [])]
    merged = list(dict.fromkeys(preferred + existing))
    persona["preferred_connectors"] = merged
    persona["domain_profile_id"] = profile.get("profile_id")
    updated["persona"] = persona
    updated["domain_preferred_connectors"] = preferred
    updated["domain_routing_applied"] = True
    subdomain = (classification.get("domain") or {}).get("subdomain_key") or (classification.get("domain") or {}).get("subdomain")
    if subdomain:
        updated["domain_subdomain"] = subdomain
    return updated


def apply_tool_selection_policy(
    tool_selection: dict[str, Any],
    classification: dict[str, Any],
    agent_persona: dict[str, Any],
) -> dict[str, Any]:
    if not is_domain_routing_active(classification):
        return tool_selection
    profile = get_domain_profile(classification)
    if not profile:
        return tool_selection
    preferred = {str(item).lower() for item in (profile.get("connector_preferences") or [])}
    preferred.update(str(item).lower() for item in (agent_persona.get("preferred_connectors") or []))

    def _rank(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        def score(tool: dict[str, Any]) -> tuple[int, str]:
            fn = tool.get("function") if isinstance(tool.get("function"), dict) else {}
            name = str(fn.get("name") or tool.get("name") or "")
            connector = name.split("_", 1)[0].lower() if "_" in name else name.lower()
            return (0 if connector in preferred else 1, name)

        return sorted(tools, key=score)

    updated = dict(tool_selection)
    updated["read_tools"] = _rank(list(updated.get("read_tools") or []))
    updated["write_tools"] = _rank(list(updated.get("write_tools") or []))
    updated["domain_routing_applied"] = True
    updated["domain_profile_id"] = profile.get("profile_id")
    return updated
