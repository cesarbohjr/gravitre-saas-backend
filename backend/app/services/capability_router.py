"""Phase B — capability-first routing: business intent → capability_id → binding."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.capability_ontology.registry import get_capability
from app.capability_ontology.resolver import CapabilityResolution, resolve_capability
from app.services.cognitive_resolution_pipeline import CognitiveResolutionResult
from app.services.connector_semantic_registry import (
    mentions_analytics_traffic_language,
    mentions_website_performance_language,
    resolve_analytics_capabilities_for_message,
    resolve_connector_from_text,
)

_WRITE_HINT = re.compile(
    r"\b(send|post|create|add|update|delete|remove|schedule|refund|invite|assign)\b",
    re.I,
)
_SEARCH_HINT = re.compile(r"\b(search|find|lookup|list|show me)\b", re.I)
_EMAIL_HINT = re.compile(r"\b(email|e-mail|mail)\b", re.I)
_SLACK_HINT = re.compile(r"\b(slack|channel)\b", re.I)
_CRM_HINT = re.compile(r"\b(contact|lead|crm|hubspot|salesforce|pipedrive)\b", re.I)


@dataclass(frozen=True)
class CapabilityRoute:
    capability_id: str
    resolution: CapabilityResolution | None
    reason: str

    @property
    def ok(self) -> bool:
        return bool(self.capability_id) and (
            self.resolution is None or self.resolution.ok or not self.resolution.ambiguous
        )


def _intent_class_from_task_state(task_state: dict[str, Any] | None) -> str | None:
    state = task_state if isinstance(task_state, dict) else {}
    needs = state.get("cognitive_resolution_needs")
    if not isinstance(needs, dict):
        return None
    reason = str(needs.get("reason") or "").strip()
    if reason in {"chitchat", "simple_math", "general_knowledge"}:
        return reason
    if reason.startswith("reference_"):
        return reason
    return reason or None


def route_capability_for_turn(
    message: str,
    *,
    task_state: dict[str, Any] | None,
    connected_integrations: list[str] | None,
    classification: dict[str, Any] | None = None,
    cognitive_resolution: CognitiveResolutionResult | None = None,
) -> CapabilityRoute | None:
    """Resolve a canonical capability for this turn when signals are strong enough."""
    text = (message or "").strip()
    connected = {str(c).strip().lower() for c in (connected_integrations or []) if str(c).strip()}
    cls = classification if isinstance(classification, dict) else {}
    state = task_state if isinstance(task_state, dict) else {}

    intent_class = _intent_class_from_task_state(state)
    if intent_class in {"chitchat", "simple_math", "general_knowledge"}:
        return None

    analytics_caps = tuple(
        cognitive_resolution.analytics_capabilities
        if cognitive_resolution is not None
        else resolve_analytics_capabilities_for_message(text, connected_integrations=connected)
    )
    if analytics_caps or mentions_analytics_traffic_language(text) or mentions_website_performance_language(text):
        if connected and "google_analytics" in connected.intersection(analytics_caps or {"google_analytics"}):
            cap_id = "analytics.traffic_overview"
            resolution = resolve_capability(
                cap_id,
                connected_integrations=connected,
                query=text,
                classification=cls,
            )
            return CapabilityRoute(capability_id=cap_id, resolution=resolution, reason="analytics_traffic")

    connector_id = (
        cognitive_resolution.connector_id
        if cognitive_resolution is not None and cognitive_resolution.connector_id
        else resolve_connector_from_text(text)
    )

    cap_id: str | None = None
    reason = ""

    if _EMAIL_HINT.search(text) and _WRITE_HINT.search(text):
        cap_id, reason = "email.send", "email_write_language"
    elif _SLACK_HINT.search(text) and _WRITE_HINT.search(text):
        cap_id, reason = "messaging.channel.post", "slack_write_language"
    elif _CRM_HINT.search(text) and _WRITE_HINT.search(text):
        cap_id, reason = "crm.contact.create", "crm_write_language"
    elif _CRM_HINT.search(text) and _SEARCH_HINT.search(text):
        cap_id, reason = "crm.contact.search", "crm_search_language"
    elif connector_id == "stripe" and _WRITE_HINT.search(text) and "refund" in text.lower():
        cap_id, reason = "payment.refund", "stripe_refund_language"

    if not cap_id:
        return None

    if cap_id and get_capability(cap_id) is None:
        return None

    resolution = resolve_capability(
        cap_id,
        connected_integrations=connected,
        query=text,
        classification=cls,
    )
    if resolution.resolved_action is None and not resolution.ambiguous:
        return None
    return CapabilityRoute(capability_id=cap_id, resolution=resolution, reason=reason)


def apply_capability_route_to_classification(
    classification: dict[str, Any],
    route: CapabilityRoute | None,
    *,
    task_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge capability route + intent class into the turn classification dict."""
    merged = dict(classification)
    intent_class = _intent_class_from_task_state(task_state)
    if intent_class:
        merged["intent_class"] = intent_class
    if route is None:
        return merged
    merged["capability_id"] = route.capability_id
    merged["capability_route_reason"] = route.reason
    if route.resolution is not None:
        if route.resolution.resolved_vendor:
            merged["preferred_connector"] = route.resolution.resolved_vendor
        if route.resolution.resolved_action:
            merged["capability_action"] = route.resolution.resolved_action
    return merged
