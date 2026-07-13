"""Tests for catalog-driven connector capability analysis."""
from __future__ import annotations

from app.services.connector_capability_analysis import (
    analyze_capability_gaps,
    declared_capabilities,
    find_catalog_action_for_capability,
    parse_action_keys,
    resolve_missing_action,
)
from app.services.connector_action_workflows import format_capability_fallback_message


def test_parse_action_keys_from_chat_labels():
    keys = parse_action_keys(
        [
            "apollo.people.search — Search people",
            "apollo.lists.create - Create contact list",
        ]
    )
    assert keys == ["apollo.people.search", "apollo.lists.create"]


def test_apollo_capability_gaps_from_catalog_when_implemented():
    gaps = analyze_capability_gaps("apollo")
    assert gaps["create_list"] is True
    assert gaps["search_people"] is True
    assert gaps["add_to_list"] is True


def test_apollo_capability_gaps_from_display_list_without_create():
    available = [
        "people.search — Search people",
        "organizations.search — Search companies",
        "contacts.create — Create contact",
        "sequences.add — Add to sequence",
    ]
    gaps = analyze_capability_gaps("apollo", available)
    assert gaps["create_list"] is False
    assert gaps["search_people"] is True
    assert gaps["add_to_list"] is True


def test_resolve_missing_action_uses_catalog_entry():
    assert find_catalog_action_for_capability("apollo", "create_list") == "apollo.lists.create"
    assert resolve_missing_action("apollo", "create_list") == "apollo.lists.create"


def test_declared_capabilities_for_apollo():
    declared = declared_capabilities("apollo")
    assert "create_list" in declared
    assert "search_people" in declared


def test_capability_fallback_message_is_catalog_driven():
    message = format_capability_fallback_message(
        integration="apollo",
        intent="Create contact list (MSP prospects)",
        available_actions=[
            "people.search — Search people",
            "sequences.add — Add to sequence",
        ],
    )
    assert "cannot create Apollo lists yet" in message
    assert "Can create list? no" in message
    assert "apollo.lists.create" in message


def test_capability_fallback_when_list_create_cataloged_but_not_wired():
    """hubspot.lists.create is cataloged; fallback should say cannot create yet (not 'not cataloged')."""
    message = format_capability_fallback_message(
        integration="hubspot",
        intent="Create contact list (Enterprise leads)",
        available_actions=["contacts.search — Search contacts"],
    )
    assert "hubspot" in message.lower()
    assert "cannot create hubspot lists yet" in message.lower()
    assert "hubspot.lists.create" in message
    assert "list creation is not cataloged" not in message.lower()
