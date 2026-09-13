"""Global clarification policy — discover before ask."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.services.connector_resource_resolver import ResourceResolution
from app.services.connector_semantic_registry import connector_display_name

ClarificationReason = Literal[
    "resolved",
    "auto_selected_single",
    "ambiguous_multiple",
    "not_connected",
    "not_authorized",
    "missing_resource",
    "no_clarification_needed",
]


@dataclass(frozen=True)
class ClarificationDecision:
    should_ask: bool
    reason: ClarificationReason
    message: str | None = None


def decide_resource_clarification(
    *,
    candidate_count: int,
    resolved_display_name: str | None = None,
    candidate_labels: list[str] | None = None,
    resource_label: str = "resource",
    connector_id: str | None = None,
) -> ClarificationDecision:
    """ASK ONLY WHEN AMBIGUITY MATERIALLY CHANGES THE RESULT."""
    vendor_label = connector_display_name(connector_id) if connector_id else resource_label
    if candidate_count <= 0:
        return ClarificationDecision(
            should_ask=True,
            reason="missing_resource",
            message=f"I couldn't find a linked {resource_label} for {vendor_label} yet.",
        )
    if candidate_count == 1:
        return ClarificationDecision(
            should_ask=False,
            reason="auto_selected_single",
        )
    labels = [label.strip() for label in (candidate_labels or []) if label and label.strip()]
    if not labels:
        return ClarificationDecision(
            should_ask=True,
            reason="ambiguous_multiple",
            message=(
                f"I found {candidate_count} {resource_label}s for {vendor_label}. "
                "Which one should I use?"
            ),
        )
    joined = ", ".join(labels[:-1]) + f", and {labels[-1]}" if len(labels) > 1 else labels[0]
    return ClarificationDecision(
        should_ask=True,
        reason="ambiguous_multiple",
        message=(
            f"I found {candidate_count} {resource_label}s for {vendor_label}: {joined}. "
            "Which one should I use?"
        ),
    )


def decide_from_resource_resolution(
    resolution: ResourceResolution,
    *,
    resource_label: str | None = None,
) -> ClarificationDecision:
    """Map a resource resolution outcome to a clarification decision."""
    label = resource_label or resolution.resource_type or "resource"
    if resolution.status == "resolved":
        return ClarificationDecision(should_ask=False, reason="resolved")
    if resolution.status == "ambiguous":
        candidate_labels = [
            str(item.get("display_name") or item.get("property_id") or item.get("site_url") or item.get("customer_id") or "")
            for item in resolution.candidates
        ]
        return decide_resource_clarification(
            candidate_count=resolution.candidate_count,
            candidate_labels=candidate_labels,
            resource_label=label.replace("_", " "),
            connector_id=resolution.connector_id,
        )
    if resolution.status == "not_found":
        if resolution.resolution_reason == "connector_not_configured":
            return ClarificationDecision(
                should_ask=False,
                reason="not_connected",
                message=format_not_connected_message(resolution.connector_id),
            )
        return ClarificationDecision(
            should_ask=True,
            reason="missing_resource",
            message=f"I couldn't find a linked {label.replace('_', ' ')} for {connector_display_name(resolution.connector_id)} yet.",
        )
    if resolution.status == "not_authorized":
        return ClarificationDecision(
            should_ask=False,
            reason="not_authorized",
            message=(
                f"{connector_display_name(resolution.connector_id)} is connected but needs "
                "re-authorization. Open **Connectors** and refresh the connection."
            ),
        )
    return ClarificationDecision(
        should_ask=False,
        reason="missing_resource",
        message=(
            f"I couldn't resolve a {label.replace('_', ' ')} for "
            f"{connector_display_name(resolution.connector_id)} right now."
        ),
    )


def decide_connector_clarification(
    *,
    connected_count: int,
    connector_id: str | None = None,
    generic_term: str | None = None,
) -> ClarificationDecision:
    """When the user names a generic category (CRM, calendar) not a vendor."""
    if connected_count <= 0:
        label = generic_term or "that connector"
        return ClarificationDecision(
            should_ask=False,
            reason="not_connected",
            message=f"No connected {label} found yet. Connect one at /connectors and try again.",
        )
    if connected_count == 1 and connector_id:
        return ClarificationDecision(should_ask=False, reason="auto_selected_single")
    if connected_count > 1:
        return ClarificationDecision(
            should_ask=True,
            reason="ambiguous_multiple",
            message="You have more than one matching connection. Which one should I use?",
        )
    return ClarificationDecision(should_ask=False, reason="no_clarification_needed")


def format_not_connected_message(connector_id: str, *, display_name: str | None = None) -> str:
    label = display_name or connector_display_name(connector_id)
    return (
        f"{label} isn't connected yet. Connect it at /connectors and I can pull live data "
        "from your account."
    )


def apply_clarification_policy_to_missing_param(
    *,
    param_name: str,
    discoverable: bool,
    inferable: bool,
    has_safe_default: bool,
    ambiguity_material: bool,
    default_disclosure: str | None = None,
) -> ClarificationDecision:
    """Global missing-parameter flow: discover → infer → default → ask."""
    if discoverable or inferable or has_safe_default:
        if ambiguity_material:
            return ClarificationDecision(
                should_ask=True,
                reason="ambiguous_multiple",
                message=f"I need to know {param_name} before I can continue.",
            )
        return ClarificationDecision(should_ask=False, reason="auto_selected_single")
    if not ambiguity_material:
        return ClarificationDecision(should_ask=False, reason="no_clarification_needed")
    message = f"To continue, I need {param_name}."
    if default_disclosure:
        message = f"{message} {default_disclosure}"
    return ClarificationDecision(should_ask=True, reason="missing_resource", message=message)
