"""Phase 6 — bridge research cascade outcomes to catalog-governed connector actions."""
from __future__ import annotations

import re
from typing import Any

from app.core.logging import get_logger
from app.services.adaptive_research_cascade import ResearchScope

logger = get_logger(__name__)

_ACTION_VERBS = re.compile(
    r"\b(create|update|send|add|delete|remove|sync|export|post|schedule|assign|make)\b",
    re.I,
)

# Representative write actions per connected integration (catalog authority checked at runtime).
_RESEARCH_ACTION_HINTS: dict[str, list[tuple[str, str]]] = {
    "hubspot": [
        ("hubspot.contacts.create", "Create HubSpot contact from research"),
        ("hubspot.deals.create", "Create HubSpot deal from research"),
    ],
    "apollo": [
        ("apollo.lists.create", "Create Apollo list from research findings"),
        ("apollo.contacts.create", "Add Apollo contact from research"),
    ],
    "salesforce": [
        ("salesforce.contacts.create", "Create Salesforce contact from research"),
    ],
    "slack": [
        ("slack.chat.postMessage", "Post Slack message from research summary"),
    ],
    "zendesk": [
        ("zendesk.tickets.create", "Create Zendesk ticket from research"),
    ],
    "notion": [
        ("notion.pages.create", "Create Notion page from research"),
    ],
    "google_drive": [
        ("google_drive.files.create", "Create Google Drive file from research"),
    ],
}


def _connected_slugs(connected_integrations: list[str] | None) -> list[str]:
    return [str(item).strip().lower() for item in (connected_integrations or []) if str(item).strip()]


def _resolve_integration_from_query(query: str, connected: list[str]) -> str | None:
    from app.services.chat_connector_models import INTEGRATION_ALIASES

    lowered = (query or "").lower()
    for slug in connected:
        aliases = INTEGRATION_ALIASES.get(slug, (slug,))
        if any(alias in lowered for alias in aliases):
            return slug
    return connected[0] if connected else None


def suggest_research_actions(
    query: str,
    *,
    research_cascade: dict[str, Any],
    connected_integrations: list[str] | None,
    research_scope: str | None = None,
) -> list[dict[str, Any]]:
    """Suggest follow-up connector actions when the user expresses action intent."""
    if not _ACTION_VERBS.search(query or ""):
        return []

    connected = _connected_slugs(connected_integrations)
    if not connected:
        return []

    integration = _resolve_integration_from_query(query, connected)
    if not integration:
        return []

    from app.services.catalog_write_authority import invoke_action_requires_write_approval

    suggestions: list[dict[str, Any]] = []
    for invoke_action, label in _RESEARCH_ACTION_HINTS.get(integration, [])[:2]:
        requires_approval = invoke_action_requires_write_approval(invoke_action)
        suggestions.append(
            {
                "integration": integration,
                "invoke_action": invoke_action,
                "label": label,
                "requires_approval": requires_approval,
                "rationale": "Research context may support this connector action.",
                "source": "research_cascade",
            }
        )
    return suggestions[:3]


def attach_research_actions_to_cascade(
    cascade: dict[str, Any],
    actions: list[dict[str, Any]],
) -> dict[str, Any]:
    updated = dict(cascade)
    updated["research_actions"] = actions
    updated["has_gated_actions"] = any(bool(row.get("requires_approval")) for row in actions)
    return updated


def build_research_pending_task(action: dict[str, Any]) -> dict[str, Any] | None:
    """Materialize a connector_action pending_task for catalog-governed confirmation."""
    invoke_action = str(action.get("invoke_action") or "").strip()
    if not invoke_action:
        return None
    return {
        "type": "connector_action",
        "status": "awaiting_confirm",
        "params": {
            "invoke_action": invoke_action,
            "integration": action.get("integration"),
            "label": action.get("label"),
            "kind": "write" if action.get("requires_approval") else "read",
            "research_suggested": True,
        },
    }


def maybe_materialize_research_pending_task(
    query: str,
    *,
    research_cascade: dict[str, Any],
) -> dict[str, Any] | None:
    """When research suggests exactly one gated write, surface it for approval."""
    actions = research_cascade.get("research_actions")
    if not isinstance(actions, list) or len(actions) != 1:
        return None
    action = actions[0]
    if not isinstance(action, dict) or not action.get("requires_approval"):
        return None
    if not _ACTION_VERBS.search(query or ""):
        return None
    return build_research_pending_task(action)
