"""ECO-005 / DEC-004: 'no connected tools' must never become 'all tools'."""
from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.fixture
def matrix(monkeypatch):
    from app.services import connector_execution_matrix as module
    entries = (
        SimpleNamespace(chat_executable=True, connector_id="hubspot", action_key="hubspot.contacts.search"),
        SimpleNamespace(chat_executable=True, connector_id="slack", action_key="slack.channels.list"),
        SimpleNamespace(chat_executable=False, connector_id="other", action_key="other.unimplemented"),
    )
    monkeypatch.setattr(module, "build_connector_execution_matrix", lambda: entries)
    return module


def test_explicit_empty_connected_integrations_is_fail_closed(matrix):
    assert matrix.chat_executable_entries(connected_integrations=[]) == []


def test_omitted_connection_filter_is_catalog_mode_not_tenant_access(matrix):
    entries = matrix.chat_executable_entries()
    assert [entry.connector_id for entry in entries] == ["hubspot", "slack"]


@pytest.mark.parametrize("connected, expected", [
    (["HubSpot"], ["hubspot"]),
    (["slack"], ["slack"]),
    (["hubspot", "slack"], ["hubspot", "slack"]),
    (["missing"], []),
    (["  "], []),
])
def test_connected_filter_only_returns_matching_implemented_actions(
        matrix, connected, expected):
    assert [e.connector_id for e in matrix.chat_executable_entries(
        connected_integrations=connected)] == expected


def test_registry_keyed_cache_detects_same_size_native_action_replacement(monkeypatch):
    """ECO-005: a one-for-one registered tool swap invalidates discovery."""
    from app.services import connector_execution_matrix as module

    registry = {"hubspot.contacts.search": object()}
    partner = frozenset({"partner.first"})
    builds = []

    def fingerprint():
        return (registry, frozenset(registry), partner)

    monkeypatch.setattr(module, "registered_actions_fingerprint", fingerprint)

    @module.registry_keyed_cache
    def discover():
        builds.append(tuple(sorted(registry)))
        return tuple(sorted(registry))

    assert discover() == ("hubspot.contacts.search",)
    assert discover() == ("hubspot.contacts.search",)
    assert len(builds) == 1  # stable key sets still hit cache

    registry.pop("hubspot.contacts.search")
    registry["slack.conversations.list"] = object()  # length unchanged
    assert discover() == ("slack.conversations.list",)
    assert len(builds) == 2


def test_registry_keyed_cache_detects_same_size_partner_action_swap(monkeypatch):
    """ECO-005: dynamic partner tool availability must not go stale."""
    from app.services import connector_execution_matrix as module

    registry = {}
    partner_keys = {"partner.first"}

    monkeypatch.setattr(
        module, "registered_actions_fingerprint",
        lambda: (registry, frozenset(registry), frozenset(partner_keys)),
    )
    builds = []

    @module.registry_keyed_cache
    def discover():
        builds.append(1)
        return tuple(sorted(partner_keys))

    assert discover() == ("partner.first",)
    partner_keys.remove("partner.first")
    partner_keys.add("partner.second")  # count unchanged
    assert discover() == ("partner.second",)
    assert len(builds) == 2


def test_tool_service_registry_fingerprint_tracks_action_keys(monkeypatch):
    from app.services import tool_service
    from app.connectors.sdk import registry as sdk_registry

    native = {"hubspot.contacts.search": object()}
    monkeypatch.setattr(tool_service, "_TOOL_REGISTRY", native)
    monkeypatch.setattr(sdk_registry, "list_partner_actions", lambda: ["partner.one"])

    first = tool_service.registered_actions_fingerprint()
    assert first[1] == frozenset({"hubspot.contacts.search"})
    assert first[2] == frozenset({"partner.one"})

    native.pop("hubspot.contacts.search")
    native["slack.conversations.list"] = object()
    second = tool_service.registered_actions_fingerprint()
    assert first[0] is second[0]
    assert first[1] != second[1]
    assert len(first[1]) == len(second[1])
