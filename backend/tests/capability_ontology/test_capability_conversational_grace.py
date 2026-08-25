"""Tests for Phase 4 capability conversational grace copy."""
from __future__ import annotations

from app.capability_ontology.conversational_grace import (
    format_capability_resolved_user_message,
    message_is_graceful,
    message_mentions_vendor,
    resolved_capability_label,
)
from app.capability_ontology.registry import get_capability
from app.capability_ontology.resolver import resolve_capability


def test_resolved_capability_label_uses_binding_not_abstract_id():
    definition = get_capability("crm.contact.create")
    assert definition is not None
    resolution = resolve_capability(
        "crm.contact.create",
        connected_integrations=["hubspot"],
        args={"preferred_vendor": "hubspot"},
    )
    label = resolved_capability_label(definition, resolution)
    assert "HubSpot" in label
    assert "crm.contact.create" not in label


def test_format_capability_resolved_user_message_is_graceful():
    definition = get_capability("crm.contact.create")
    resolution = resolve_capability(
        "crm.contact.create",
        connected_integrations=["hubspot"],
        args={"preferred_vendor": "hubspot"},
    )
    message = format_capability_resolved_user_message(definition=definition, resolution=resolution)
    assert message_is_graceful(message)
    assert message_mentions_vendor(message, "hubspot")
    assert "capability__" not in message


def test_grace_rejects_internal_capability_tool_leak():
    assert not message_is_graceful("Using capability__crm__contact__create now")
