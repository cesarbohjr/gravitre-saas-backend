"""Resolve canonical capabilities to concrete catalog actions for connected vendors."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.capability_ontology.registry import CapabilityDefinition, get_capability
from app.connectors.action_catalog.tool_aliases import catalog_tool_is_implemented
from app.services.tool_service import list_registered_actions

_TOKEN = re.compile(r"[a-z0-9_]{2,}", re.I)

# Vendor tokens mentioned in user/agent text → catalog vendor id.
_VENDOR_MENTION_ALIASES: dict[str, str] = {
    "hubspot": "hubspot",
    "salesforce": "salesforce",
    "sfdc": "salesforce",
    "pipedrive": "pipedrive",
    "engagebay": "engagebay",
    "slack": "slack",
    "teams": "microsoft_teams",
    "microsoft_teams": "microsoft_teams",
    "gmail": "gmail",
    "sendgrid": "sendgrid",
    "outlook": "outlook",
    "google_calendar": "google_calendar",
    "calendar": "google_calendar",
    "google_drive": "google_drive",
    "drive": "google_drive",
    "notion": "notion",
    "stripe": "stripe",
    "workday": "workday",
    "ga4": "google_analytics",
    "google_analytics": "google_analytics",
}


@dataclass(frozen=True)
class CapabilityResolution:
    capability_id: str
    resolved_action: str | None
    resolved_vendor: str | None
    ambiguous: bool
    candidates: tuple[str, ...]
    reason: str
    resolution_method: str

    @property
    def ok(self) -> bool:
        return bool(self.resolved_action) and not self.ambiguous


def _implemented_bindings(
    definition: CapabilityDefinition,
    connected: set[str],
) -> list[tuple[str, str, str]]:
    """Return (vendor, action_key, label) for connected + implemented bindings."""
    registered = set(list_registered_actions())
    out: list[tuple[str, str, str]] = []
    for binding in definition.bindings:
        vendor = binding.vendor.strip().lower()
        if vendor not in connected:
            continue
        if not catalog_tool_is_implemented(binding.action_key, registered):
            continue
        out.append((vendor, binding.action_key, binding.label))
    return out


def _mentioned_vendors(text: str) -> set[str]:
    lowered = (text or "").lower()
    hits: set[str] = set()
    for token in _TOKEN.findall(lowered):
        if token in _VENDOR_MENTION_ALIASES:
            hits.add(_VENDOR_MENTION_ALIASES[token])
    return hits


def _preferred_vendor_from_context(
    *,
    query: str,
    classification: dict[str, Any] | None,
    args: dict[str, Any] | None,
    agent_systems: list[str] | None,
) -> str | None:
    args = args or {}
    for key in ("preferred_vendor", "vendor", "integration", "connector"):
        raw = str(args.get(key) or "").strip().lower()
        if raw:
            return _VENDOR_MENTION_ALIASES.get(raw, raw)

    cls = classification or {}
    for key in ("preferred_connector", "integration", "connector", "channel_override"):
        raw = str(cls.get(key) or "").strip().lower()
        if raw:
            return _VENDOR_MENTION_ALIASES.get(raw, raw)

    mentions = _mentioned_vendors(query)
    if len(mentions) == 1:
        return next(iter(mentions))

    systems = [str(s).strip().lower() for s in (agent_systems or []) if str(s).strip()]
    if len(systems) == 1:
        return _VENDOR_MENTION_ALIASES.get(systems[0], systems[0])

    return None


def resolve_capability(
    capability_id: str,
    *,
    connected_integrations: list[str] | None,
    query: str = "",
    classification: dict[str, Any] | None = None,
    args: dict[str, Any] | None = None,
    agent_systems: list[str] | None = None,
) -> CapabilityResolution:
    """Resolve a canonical capability to one implemented catalog action."""
    cap_id = str(capability_id or "").strip().lower()
    definition = get_capability(cap_id)
    if not definition:
        return CapabilityResolution(
            capability_id=cap_id,
            resolved_action=None,
            resolved_vendor=None,
            ambiguous=False,
            candidates=(),
            reason="unknown_capability",
            resolution_method="none",
        )

    connected = {str(c).strip().lower() for c in (connected_integrations or []) if str(c).strip()}
    bindings = _implemented_bindings(definition, connected)
    candidates = tuple(action for _, action, _ in bindings)

    if not bindings:
        return CapabilityResolution(
            capability_id=cap_id,
            resolved_action=None,
            resolved_vendor=None,
            ambiguous=False,
            candidates=(),
            reason="no_connected_implemented_binding",
            resolution_method="none",
        )

    if len(bindings) == 1:
        vendor, action, _ = bindings[0]
        return CapabilityResolution(
            capability_id=cap_id,
            resolved_action=action,
            resolved_vendor=vendor,
            ambiguous=False,
            candidates=candidates,
            reason="single_connected_vendor",
            resolution_method="connected_only",
        )

    preferred = _preferred_vendor_from_context(
        query=query,
        classification=classification,
        args=args,
        agent_systems=agent_systems,
    )
    if preferred:
        for vendor, action, _ in bindings:
            if vendor == preferred:
                return CapabilityResolution(
                    capability_id=cap_id,
                    resolved_action=action,
                    resolved_vendor=vendor,
                    ambiguous=False,
                    candidates=candidates,
                    reason=f"preferred_vendor:{preferred}",
                    resolution_method="preferred_vendor",
                )

    mentions = _mentioned_vendors(query)
    matched = [row for row in bindings if row[0] in mentions]
    if len(matched) == 1:
        vendor, action, _ = matched[0]
        return CapabilityResolution(
            capability_id=cap_id,
            resolved_action=action,
            resolved_vendor=vendor,
            ambiguous=False,
            candidates=candidates,
            reason=f"query_mention:{vendor}",
            resolution_method="query_mention",
        )

    return CapabilityResolution(
        capability_id=cap_id,
        resolved_action=None,
        resolved_vendor=None,
        ambiguous=True,
        candidates=candidates,
        reason="multiple_connected_vendors",
        resolution_method="ambiguous",
    )


def resolve_capability_invoke_action(
    action_or_capability: str,
    *,
    connected_integrations: list[str] | None,
    query: str = "",
    classification: dict[str, Any] | None = None,
    args: dict[str, Any] | None = None,
) -> CapabilityResolution | None:
    """If ``action_or_capability`` is a capability id, resolve it; else None."""
    raw = str(action_or_capability or "").strip()
    if raw.startswith("capability."):
        cap_id = raw.removeprefix("capability.").strip().lower()
        return resolve_capability(
            cap_id,
            connected_integrations=connected_integrations,
            query=query,
            classification=classification,
            args=args,
        )
    if get_capability(raw):
        return resolve_capability(
            raw,
            connected_integrations=connected_integrations,
            query=query,
            classification=classification,
            args=args,
        )
    return None
