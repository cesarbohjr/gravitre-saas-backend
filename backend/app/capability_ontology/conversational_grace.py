"""Natural user-facing copy when capability tools resolve to vendor actions (Phase 4)."""
from __future__ import annotations

from app.capability_ontology.registry import CapabilityDefinition
from app.capability_ontology.resolver import CapabilityResolution


def vendor_display_label(vendor: str | None) -> str:
    text = str(vendor or "").strip().replace("_", " ")
    return text.title() if text else "your connected app"


def resolved_capability_label(
    definition: CapabilityDefinition | None,
    resolution: CapabilityResolution,
) -> str:
    """Prefer vendor-specific binding label over abstract capability name."""
    if definition is None:
        return "this action"
    if resolution.resolved_vendor and resolution.resolved_action:
        for binding in definition.bindings:
            if (
                binding.vendor == resolution.resolved_vendor
                and binding.action_key == resolution.resolved_action
            ):
                return binding.label
        vendor = vendor_display_label(resolution.resolved_vendor)
        return f"{definition.label} in {vendor}"
    return definition.label


def format_capability_resolved_user_message(
    *,
    definition: CapabilityDefinition | None,
    resolution: CapabilityResolution,
    action_verb: str = "run",
) -> str:
    """Operator-facing sentence — no internal capability ids or tool names."""
    label = resolved_capability_label(definition, resolution)
    vendor = vendor_display_label(resolution.resolved_vendor)
    if resolution.resolved_vendor:
        return f"I'll {action_verb} that in your {vendor} ({label})."
    return f"I'll {action_verb} {label} once a connector is connected."


def message_is_graceful(text: str) -> bool:
    """True when copy avoids leaking internal capability tool identifiers."""
    lowered = str(text or "").lower()
    if "capability__" in lowered:
        return False
    if "capability." in lowered and "crm." in lowered:
        return False
    return True


def message_mentions_vendor(text: str, vendor: str | None) -> bool:
    if not vendor:
        return False
    token = vendor.replace("_", " ").lower()
    return token in str(text or "").lower()
